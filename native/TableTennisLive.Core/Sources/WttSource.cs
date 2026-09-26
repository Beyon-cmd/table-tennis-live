using System.Collections.Concurrent;
using System.Text.Json;
using TableTennisLive.Core.Models;
using TableTennisLive.Core.Services;

namespace TableTennisLive.Core.Sources;

/// <summary>WTT official public JSON feed. No missing score is inferred.</summary>
public sealed class WttSource : IMatchSource, IDisposable
{
    private const string Front = "https://wtt-web-frontdoor-cthahjeqhbh6aqe3.a01.azurefd.net";
    private const string LiveEvents = Front + "/websitestaticapifiles/general/wtt_live_results_event_id.json";
    private const string EventCatalog = Front + "/websitestaticapifiles/general/wtt_upcoming_only_events_list.json";
    private readonly OfficialJson _json = new();
    private readonly Dictionary<int, IReadOnlyList<Match>> _eventCache = [];
    private readonly Dictionary<int, TimeSpan> _offsets = [];
    private readonly ConcurrentDictionary<string, Match> _detailCache = new();
    private readonly ConcurrentDictionary<string, string> _documentCodes = new();
    private IReadOnlyList<Match> _current = [];
    public string Name => "WTT";

    public async Task<IReadOnlyList<Match>> GetMatchesAsync(CancellationToken ct)
    {
        var events = await GetEventsAsync(ct).ConfigureAwait(false);
        var result = new List<Match>();
        var failures = 0;
        foreach (var (id, name) in events)
        {
            try
            {
                var rows = await GetEventMatchesAsync(id, name, ct).ConfigureAwait(false);
                _eventCache[id] = rows;
                result.AddRange(rows);
            }
            catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
            catch
            {
                failures++;
                if (_eventCache.TryGetValue(id, out var old))
                    result.AddRange(old.Select(match => match with { DataStale = true }));
            }
        }
        if (events.Count > 0 && failures == events.Count && result.Count == 0)
            throw new IOException("所有 WTT 赛事取数失败");
        for (var index = 0; index < result.Count; index++)
        {
            if (!_detailCache.TryGetValue(result[index].Id, out var detail)) continue;
            var merged = PreferRichDetail(result[index], detail);
            if (ReferenceEquals(merged, result[index])) _detailCache.TryRemove(result[index].Id, out _);
            else result[index] = merged;
        }
        _current = result;
        return result;
    }

    public async Task<Match?> GetDetailAsync(string id, CancellationToken ct)
    {
        var known = _current.FirstOrDefault(m => m.Id == id);
        if (known is null) return null;
        var parts = id.Split(':', 3);
        if (parts.Length != 3 || !int.TryParse(parts[1], out var eventId) ||
            eventId <= 0 || parts[2].Length == 0) return known;

        // The schedule and recent-results feed can contain only the overall result.
        // Request the official match-centre card when the user opens its detail.
        var code = _documentCodes.TryGetValue(id, out var original) ? original : parts[2];
        var card = await MatchCardAsync(eventId, code, false, ct).ConfigureAwait(false);
        if (card.ValueKind != JsonValueKind.Object && code != parts[2])
            card = await MatchCardAsync(eventId, parts[2], false, ct).ConfigureAwait(false);
        var detail = MergeDetail(known, card);
        if (!ReferenceEquals(detail, known)) _detailCache[id] = detail;
        return detail;
    }

    public static Match PreferRichDetail(Match incoming, Match detail)
    {
        if (incoming.Id != detail.Id || incoming.Sets.Count >= detail.Sets.Count ||
            incoming.ScoreA + incoming.ScoreB > detail.ScoreA + detail.ScoreB)
            return incoming;
        return detail with
        {
            Status = incoming.Status == MatchStatus.Finished || detail.Status == MatchStatus.Finished
                ? MatchStatus.Finished : incoming.Status,
            DataStale = incoming.DataStale,
            LastUpdate = incoming.LastUpdate
        };
    }

    public static Match MergeDetail(Match known, JsonElement card)
    {
        var score = ParseScore(card);
        if (score is null) return known;
        if (score.Value.Sets.Count < known.Sets.Count ||
            score.Value.A + score.Value.B < known.ScoreA + known.ScoreB &&
            score.Value.Sets.Count <= known.Sets.Count)
            return known;
        var sets = score.Value.Sets.Count >= known.Sets.Count
            ? score.Value.Sets : known.Sets;
        var reconciled = ReconcileScore(score.Value.A, score.Value.B, sets);
        var status = known.Status;
        if (new[] { "OFFICIAL", "FINISHED", "FINAL" }.Contains(
            card.At("resultStatus").Text().ToUpperInvariant()))
            status = MatchStatus.Finished;

        SetScore? current = null;
        if (status == MatchStatus.Live && sets.Count > reconciled.A + reconciled.B)
        {
            current = sets[reconciled.A + reconciled.B];
            sets = sets.Take(reconciled.A + reconciled.B).ToArray();
        }
        else if (status == MatchStatus.Live && sets.Count == known.Sets.Count)
            current = known.CurrentSet;
        return known with
        {
            Status = status,
            ScoreA = reconciled.A,
            ScoreB = reconciled.B,
            ScoreKnown = true,
            ScoreReconciled = reconciled.Reconciled,
            Sets = sets,
            CurrentSet = current,
            LastUpdate = DateTimeOffset.Now
        };
    }

    private static bool MainEvent(string name)
    {
        var low = name.ToLowerInvariant();
        if (low.Contains("youth smash")) return false;
        return low.Contains("smash") || low.StartsWith("wtt ") && low.Contains("finals") ||
               low.Contains("wtt champions") || low.Contains("wtt star contender") ||
               low.Contains("wtt contender");
    }

    private async Task<IReadOnlyList<(int Id, string Name)>> GetEventsAsync(CancellationToken ct)
    {
        var primaryFailed = false;
        try
        {
            var rows = await _json.GetAsync(LiveEvents, "events", TimeSpan.FromSeconds(120), ct);
            if (rows.Items().Any())
                return rows.Items().Where(r => MainEvent(r.At("eventName").Text()))
                    .Select(r => (r.At("eventId").Number(), r.At("eventName").Text()))
                    .Where(r => r.Item1 > 0).ToArray();
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
        catch { primaryFailed = true; }
        var catalog = await _json.GetAsync(EventCatalog, "events_fallback", TimeSpan.FromMinutes(10), ct);
        var now = DateTime.Now;
        var picked = catalog.Items().Where(r => MainEvent(r.At("eventName").Text()))
            .Where(r => DateTime.TryParse(r.At("startDateTime").Text(), out var start) &&
                        DateTime.TryParse(r.At("endDateTime").Text(), out var end) &&
                        start <= now.AddDays(1) && end >= now.AddDays(-1))
            .Select(r => (r.At("eventId").Number(), r.At("eventName").Text()))
            .Where(r => r.Item1 > 0).Take(3).ToArray();
        if (primaryFailed && picked.Length == 0 && _eventCache.Count > 0)
            throw new IOException("WTT 实时赛事列表暂不可用");
        return picked;
    }

    private async Task<TimeSpan?> EventOffsetAsync(int id, CancellationToken ct)
    {
        if (_offsets.TryGetValue(id, out var offset)) return offset;
        var rows = await _json.GetAsync(EventCatalog, "events_fallback", TimeSpan.FromMinutes(10), ct);
        var row = rows.Items().FirstOrDefault(r => r.At("eventId").Number() == id);
        var value = WttVenueTime.Offset(row);
        if (value is not null) _offsets[id] = value.Value;
        return value;
    }

    private async Task<IReadOnlyList<Match>> GetEventMatchesAsync(int id, string name, CancellationToken ct)
    {
        var offset = await EventOffsetAsync(id, ct).ConfigureAwait(false);
        if (offset is null) throw new InvalidDataException("WTT 场馆时区未核实");
        var schedule = await _json.GetAsync($"{Front}/websitecacheddata/{id}/schedule/schedule.json",
            $"sched-{id}", TimeSpan.FromSeconds(60), ct).ConfigureAwait(false);
        var units = schedule.Items().SelectMany(c => c.At("Competition").At("Unit").Items()).ToArray();
        var live = await LiveIdsAsync(id, ct).ConfigureAwait(false);
        var liveCards = new ConcurrentDictionary<string, JsonElement>();
        await Parallel.ForEachAsync(live, new ParallelOptions { MaxDegreeOfParallelism = 4,
            CancellationToken = ct }, async (entry, token) =>
        {
            var card = await MatchCardAsync(id, entry.Value, false, token).ConfigureAwait(false);
            if (card.ValueKind == JsonValueKind.Object) liveCards[entry.Key] = card;
        }).ConfigureAwait(false);
        var minimal = await ResultMinimalAsync(id, ct).ConfigureAwait(false);
        var results = await RecentResultsAsync(id, ct).ConfigureAwait(false);
        foreach (var (key, raw) in live)
            _documentCodes[$"wtt:{id}:{key}"] = raw;
        foreach (var (key, row) in minimal)
        {
            var raw = row.At("documentCode").Text();
            if (raw.Length > 0) _documentCodes[$"wtt:{id}:{key}"] = raw;
        }
        var missing = minimal.Where(entry => !results.ContainsKey(entry.Key)).ToArray();
        await Parallel.ForEachAsync(missing, new ParallelOptions { MaxDegreeOfParallelism = 8,
            CancellationToken = ct }, async (entry, token) =>
        {
            var card = await MatchCardAsync(id, entry.Value.At("documentCode").Text(), true, token)
                .ConfigureAwait(false);
            if (ParseScore(card) is not null) results[entry.Key] = card;
        }).ConfigureAwait(false);
        var now = DateTimeOffset.Now;
        var output = new List<Match>();
        var seen = new HashSet<string>();
        foreach (var (key, card) in liveCards)
        {
            var match = FromCard(id, name, key, card, default, offset, now, live: true);
            if (match is not null) output.Add(match);
            seen.Add(key);
        }
        foreach (var unit in units)
        {
            var key = Normalize(unit.At("Code").Text());
            if (key.Length == 0 || !seen.Add(key)) continue;
            _documentCodes.TryAdd($"wtt:{id}:{key}", unit.At("Code").Text());
            liveCards.TryGetValue(key, out var liveCard);
            results.TryGetValue(key, out var result);
            minimal.TryGetValue(key, out var resultRow);
            var match = FromUnit(id, name, unit, live.ContainsKey(key), liveCard, result,
                resultRow, offset, now);
            if (match is not null) output.Add(match);
        }
        foreach (var (key, card) in results)
        {
            if (!seen.Add(key)) continue;
            minimal.TryGetValue(key, out var resultRow);
            var match = FromCard(id, name, key, card, resultRow, offset, now, live: false);
            if (match is not null) output.Add(match);
        }
        return output;
    }

    private async Task<Dictionary<string, string>> LiveIdsAsync(int id, CancellationToken ct)
    {
        try
        {
            var rows = await _json.GetAsync($"{Front}/websitestaticapifiles/running-events/{id}/{id}_livematchids.json",
                $"live-{id}", TimeSpan.FromSeconds(1), ct).ConfigureAwait(false);
            return rows.Items().Select(item => item.ValueKind == JsonValueKind.Object ? item.At("d").Text() : item.Text())
                .Where(code => code.Length > 0).Distinct().ToDictionary(Normalize);
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
        catch { return []; }
    }

    private async Task<JsonElement> MatchCardAsync(int id, string code, bool finished, CancellationToken ct)
    {
        var key = $"match-{id}-{code}";
        try
        {
            var card = await _json.GetAsync($"{Front}/matchdata/matchcentre/{id}/{code}.json", key,
                finished ? TimeSpan.FromDays(1) : TimeSpan.FromSeconds(1), ct).ConfigureAwait(false);
            if (finished && ParseScore(card) is null) _json.Evict(key);
            return card;
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
        catch { return default; }
    }

    private async Task<Dictionary<string, JsonElement>> ResultMinimalAsync(int id, CancellationToken ct)
    {
        try
        {
            var rows = await _json.GetAsync($"{Front}/websitecacheddata/{id}/officialresult/officialresult_minimal.json",
                $"result-min-{id}", TimeSpan.FromSeconds(120), ct).ConfigureAwait(false);
            return rows.Items().Where(r => r.At("documentCode").Text().Length > 0)
                .ToDictionary(r => Normalize(r.At("documentCode").Text()), r => r);
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
        catch { return []; }
    }

    private async Task<ConcurrentDictionary<string, JsonElement>> RecentResultsAsync(int id, CancellationToken ct)
    {
        var results = new ConcurrentDictionary<string, JsonElement>();
        try
        {
            var rows = await _json.GetAsync($"{Front}/websitestaticapifiles/{id}/{id}_take_10_official_results.json",
                $"results-{id}", TimeSpan.FromSeconds(120), ct).ConfigureAwait(false);
            foreach (var row in rows.Items())
            {
                var card = row.At("match_card");
                var code = Normalize(card.At("documentCode").Text());
                if (code.Length == 0) code = Normalize(row.At("documentCode").Text());
                if (code.Length > 0) results[code] = card.ValueKind == JsonValueKind.Object ? card : row;
            }
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
        catch { }
        return results;
    }

    private static string Normalize(string code) => code.TrimEnd('-');

    private static Match? FromUnit(int id, string name, JsonElement unit, bool live,
        JsonElement liveCard, JsonElement result, JsonElement resultRow, TimeSpan? offset,
        DateTimeOffset now)
    {
        var key = Normalize(unit.At("Code").Text());
        var start = WttVenueTime.ToLocal(unit.At("StartDate").Text(), offset);
        if (key.Length == 0 || start is null) return null;
        var players = unit.At("StartList").At("Start").Items().Take(2)
            .Select(row => row.At("Competitor")).ToArray();
        if (players.Length != 2) return null;
        var names = players.Select(player => player.At("Description").At("TeamName").Text())
            .ToArray();
        if (names.Any(n => n.Length == 0 || n == "TBD")) return null;
        var orgs = players.Select(player => player.At("Organization").Text()).ToArray();
        var statusRaw = unit.At("ScheduleStatus").Text();
        var status = result.ValueKind == JsonValueKind.Object || statusRaw == "Official"
            ? MatchStatus.Finished : live ? MatchStatus.Live : MatchStatus.Upcoming;
        var card = result.ValueKind == JsonValueKind.Object ? result : liveCard;
        var score = ParseScore(card);
        var corrected = score is null ? (A: 0, B: 0, Reconciled: false)
            : ReconcileScore(score.Value.A, score.Value.B, score.Value.Sets);
        if (result.ValueKind == JsonValueKind.Object)
        {
            names = CardNames(result, names);
            var resultStart = WttVenueTime.ToLocal(resultRow.At("startDateLocal").Text(), offset);
            if (resultStart is not null) start = resultStart;
        }
        if (status == MatchStatus.Upcoming && (start < now.AddHours(-12) || start > now.AddHours(24)))
            return null;
        var sets = score?.Sets ?? [];
        SetScore? current = null;
        if (status == MatchStatus.Live && score is not null && sets.Count > corrected.A + corrected.B)
        {
            current = sets[corrected.A + corrected.B];
            sets = sets.Take(corrected.A + corrected.B).ToArray();
        }
        else if (status != MatchStatus.Live && score is not null && sets.Count > corrected.A + corrected.B)
            sets = sets.Take(corrected.A + corrected.B).ToArray();
        var sub = unit.At("SubEvent").Text();
        return new Match($"wtt:{id}:{key}", "WTT", sub.Length > 0 ? $"{name} · {sub}" : name,
            status, start.Value, WithOrg(names[0], orgs[0]), WithOrg(names[1], orgs[1]))
        {
            ScoreA = corrected.A, ScoreB = corrected.B, Sets = sets,
            CurrentSet = current, ScoreKnown = score is not null, LastUpdate = now,
            PlayerARaw = names[0], PlayerBRaw = names[1], ScoreReconciled = corrected.Reconciled
        };
    }

    private static Match? FromCard(int id, string name, string key, JsonElement card,
        JsonElement resultRow, TimeSpan? offset, DateTimeOffset now, bool live)
    {
        var names = CardNames(card, ["", ""]);
        if (names.Any(n => n.Length == 0)) return null;
        var score = ParseScore(card);
        var corrected = score is null ? (A: 0, B: 0, Reconciled: false)
            : ReconcileScore(score.Value.A, score.Value.B, score.Value.Sets);
        var start = WttVenueTime.ToLocal(resultRow.At("startDateLocal").Text(), offset) ?? now;
        if (DateTimeOffset.TryParse(card.At("matchStartTimeUTC").Text(), out var utcStart))
            start = utcStart.ToLocalTime();
        var final = new[] { "OFFICIAL", "FINISHED", "FINAL" }
            .Contains(card.At("resultStatus").Text().ToUpperInvariant());
        var status = live && !final ? MatchStatus.Live : MatchStatus.Finished;
        var sets = score?.Sets ?? [];
        SetScore? current = null;
        if (status == MatchStatus.Live && score is not null && sets.Count > corrected.A + corrected.B)
        {
            current = sets[corrected.A + corrected.B];
            sets = sets.Take(corrected.A + corrected.B).ToArray();
        }
        var sub = card.At("subEventName").Text();
        if (sub.Length == 0) sub = resultRow.At("subEventType").Text();
        return new Match($"wtt:{id}:{key}", "WTT", sub.Length > 0 ? $"{name} · {sub}" : name,
            status, start, names[0], names[1])
        {
            ScoreA = corrected.A, ScoreB = corrected.B, Sets = sets,
            CurrentSet = current, ScoreKnown = score is not null, LastUpdate = now,
            PlayerARaw = names[0], PlayerBRaw = names[1], ScoreReconciled = corrected.Reconciled
        };
    }

    private static string WithOrg(string name, string org) => org.Length == 0 ? name : $"{name} ({org})";

    private static string[] CardNames(JsonElement card, string[] fallback)
    {
        var players = card.At("competitiors").Items().Take(2).ToArray();
        if (players.Length != 2) return fallback;
        return players.Select((player, i) =>
        {
            var raw = player.At("competitiorName").Text();
            return raw.Length == 0 ? fallback[i] : WithOrg(raw, player.At("competitiorOrg").Text());
        }).ToArray();
    }

    private static (int A, int B, IReadOnlyList<SetScore> Sets)? ParseScore(JsonElement card)
    {
        if (card.ValueKind != JsonValueKind.Object) return null;
        var body = card.At("matchCardResult");
        if (body.ValueKind != JsonValueKind.Object) body = card;
        var inner = body.At("match_result");
        if (inner.ValueKind == JsonValueKind.Object) body = inner;
        var overall = First(body, "OverallScores", "overallScores", "resultOverallScores");
        var games = First(body, "GameScores", "gameScores", "ResultsGameScores", "resultsGameScores");
        var score = Pair(overall);
        if (overall.ValueKind != JsonValueKind.Undefined && score is null) return null;
        var sets = games.ValueKind == JsonValueKind.Array
            ? games.Items().Select(Pair).Where(p => p is not null).Select(p => p!).ToArray()
            : games.Text().Split(',').Select(part => Pair(part)).Where(p => p is not null).Select(p => p!).ToArray();
        sets = sets.Where(p => p.Left != 0 || p.Right != 0).ToArray();
        return score is null && sets.Length == 0 ? null : (score?.Left ?? 0, score?.Right ?? 0, sets);
    }

    public static (int A, int B, bool Reconciled) ReconcileScore(int a, int b,
        IReadOnlyList<SetScore> sets)
    {
        var wonA = sets.Count(s => s.Left >= 11 && s.Left - s.Right >= 2);
        var wonB = sets.Count(s => s.Right >= 11 && s.Right - s.Left >= 2);
        return wonA + wonB > a + b ? (wonA, wonB, true) : (a, b, false);
    }

    private static JsonElement First(JsonElement element, params string[] keys)
    {
        foreach (var key in keys)
        {
            var value = element.At(key);
            if (value.ValueKind != JsonValueKind.Undefined && value.ValueKind != JsonValueKind.Null)
                return value;
        }
        return default;
    }

    private static SetScore? Pair(JsonElement value)
    {
        if (value.ValueKind == JsonValueKind.Object)
        {
            var left = value.At("HomePeriodScore");
            var right = value.At("AwayPeriodScore");
            if (left.ValueKind != JsonValueKind.Undefined && right.ValueKind != JsonValueKind.Undefined)
                return new(left.Number(), right.Number());
        }
        return Pair(value.Text());
    }

    private static SetScore? Pair(string value)
    {
        var match = System.Text.RegularExpressions.Regex.Match(value, @"(\d+)\s*[-:]\s*(\d+)");
        return match.Success ? new(int.Parse(match.Groups[1].Value), int.Parse(match.Groups[2].Value)) : null;
    }

    public void Dispose() => _json.Dispose();
}
