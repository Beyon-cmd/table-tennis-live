using System.IO.Compression;
using System.Text;
using System.Text.Json;
using TableTennisLive.Core.Models;
using TableTennisLive.Core.Services;

namespace TableTennisLive.Core.Sources;

/// <summary>2026 Aichi-Nagoya official table tennis results.</summary>
public sealed class AsianGamesSource : IMatchSource, IDisposable
{
    private const string Base = "https://back.results.asiangames2026.org/s/AG2026/en/TTE";
    private static readonly DateOnly FirstDay = new(2026, 9, 20);
    private static readonly DateOnly LastDay = new(2026, 9, 28);
    private static readonly TimeZoneInfo Japan = TimeZoneInfo.CreateCustomTimeZone("JST", TimeSpan.FromHours(9), "JST", "JST");
    private readonly HttpClient _http = new(new HttpClientHandler { AllowAutoRedirect = true })
    { Timeout = TimeSpan.FromSeconds(12) };
    private readonly Dictionary<DateOnly, (DateTimeOffset Time, IReadOnlyList<Match> Rows)> _cache = [];
    private IReadOnlyDictionary<string, Match> _current = new Dictionary<string, Match>();
    public string Name => "majors";

    public AsianGamesSource()
    {
        _http.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0");
        _http.DefaultRequestHeaders.Referrer = new Uri("https://results.asiangames2026.org/");
    }

    public async Task<IReadOnlyList<Match>> GetMatchesAsync(CancellationToken ct)
    {
        var today = DateOnly.FromDateTime(TimeZoneInfo.ConvertTime(DateTimeOffset.UtcNow, Japan).DateTime);
        if (today < FirstDay.AddDays(-1) || today > LastDay.AddDays(1)) return [];
        var output = new List<Match>();
        foreach (var day in new[] { today.AddDays(-1), today, today.AddDays(1) })
        {
            if (day < FirstDay || day > LastDay) continue;
            _cache.TryGetValue(day, out var cached);
            var ttl = day == today
                ? cached.Rows?.Any(m => m.Status == MatchStatus.Live) == true ? 2 : 8
                : 90;
            if (cached.Rows is not null && DateTimeOffset.UtcNow - cached.Time < TimeSpan.FromSeconds(ttl))
            {
                output.AddRange(cached.Rows);
                continue;
            }
            try
            {
                var payload = await FetchAsync($"{Base}/schedule/daily/{day:yyyy-MM-dd}", ct)
                    .ConfigureAwait(false);
                if (payload.ValueKind != JsonValueKind.Array)
                    throw new InvalidDataException("亚运会官方赛程格式异常");
                var rows = payload.Items().Select(ParseSchedule).OfType<Match>().ToArray();
                _cache[day] = (DateTimeOffset.UtcNow, rows);
                output.AddRange(rows);
            }
            catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
            catch
            {
                if (cached.Rows is null) throw;
                output.AddRange(cached.Rows.Select(m => m with { DataStale = true }));
            }
        }
        _current = output.ToDictionary(m => m.Id);
        return output;
    }

    public async Task<Match?> GetDetailAsync(string id, CancellationToken ct)
    {
        if (!_current.TryGetValue(id, out var match)) return null;
        if (!match.Competition.Contains("团体")) return match;
        var key = Uri.EscapeDataString(id["asiangames:".Length..]);
        var payload = await FetchAsync($"{Base}/results/{key}", ct).ConfigureAwait(false);
        if (payload.ValueKind != JsonValueKind.Object) return match;
        var homeOrg = payload.At("Competitors").Items().FirstOrDefault().At("Org").Text();
        var games = new List<TeamGame>();
        foreach (var unit in payload.At("SubUnits").Items())
        {
            var players = unit.At("Competitors").Items().Take(2).ToArray();
            if (players.Length < 2) continue;
            var leftIndex = Array.FindIndex(players, p => p.At("Org").Text() == homeOrg);
            if (leftIndex < 0) leftIndex = 0;
            var left = players[leftIndex];
            var right = players[1 - leftIndex];
            var sets = unit.At("Results").At("Periods").Items()
                .Where(p => p.At("ResHome").Text().Length > 0 && p.At("ResAway").Text().Length > 0)
                .Select(p => new SetScore(p.At("ResHome").Number(), p.At("ResAway").Number()))
                .Where(s => s.Left != 0 || s.Right != 0).ToArray();
            games.Add(new(left.At("Name").Text(), right.At("Name").Text(),
                left.At("Result").Number(), right.At("Result").Number(), sets));
        }
        return match with { Games = games };
    }

    public Task<JsonElement> GetBracketPayloadAsync(string projectCode, CancellationToken ct) =>
        FetchAsync($"{Base}/brackets/{Uri.EscapeDataString(projectCode)}", ct);

    private async Task<JsonElement> FetchAsync(string url, CancellationToken ct)
    {
        using var response = await _http.GetAsync(url, ct).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        var bytes = await response.Content.ReadAsByteArrayAsync(ct).ConfigureAwait(false);
        try { return JsonDocument.Parse(bytes).RootElement.Clone(); }
        catch (JsonException)
        {
            // The CDN sometimes converts zlib bytes through Latin-1 into UTF-8 text.
            var repaired = Encoding.Latin1.GetBytes(Encoding.UTF8.GetString(bytes));
            using var input = new MemoryStream(repaired);
            using var zlib = new ZLibStream(input, CompressionMode.Decompress);
            using var document = await JsonDocument.ParseAsync(zlib, cancellationToken: ct)
                .ConfigureAwait(false);
            return document.RootElement.Clone();
        }
    }

    public static Match? ParseSchedule(JsonElement row)
    {
        if (row.ValueKind != JsonValueKind.Object || row.At("IsPhase").Flag()) return null;
        var key = row.At("Key").Text();
        var left = row.At("Home");
        var right = row.At("Away");
        if (key.Length == 0 || left.At("Name").Text().Length == 0 || right.At("Name").Text().Length == 0 ||
            !DateTimeOffset.TryParse(row.At("DateTimeRaw").Text(), out var start)) return null;
        var state = row.At("Status").Text().ToUpperInvariant();
        var status = row.At("IsLive").Flag() || new[] { "LIVE", "RUNNING", "IN_PROGRESS" }.Contains(state)
            ? MatchStatus.Live
            : new[] { "OFFICIAL", "UNOFFICIAL", "FINISHED", "COMPLETED" }.Contains(state)
                ? MatchStatus.Finished : MatchStatus.Upcoming;
        var team = row.At("Type").Text() == "T" || row.At("Event").Text().Contains(".TEAM");
        var eventName = row.At("EventDesc").Text() switch
        {
            "Men's Singles" => "男子单打", "Women's Singles" => "女子单打",
            "Men's Doubles" => "男子双打", "Women's Doubles" => "女子双打",
            "Mixed Doubles" => "混合双打", "Men's Team" => "男子团体",
            "Women's Team" => "女子团体", var raw when raw.Length > 0 => raw,
            _ => "乒乓球"
        };
        var names = team ? new[] { CountryName(left), CountryName(right) }
            : new[] { left.At("Name").Text(), right.At("Name").Text() };
        var completed = new List<SetScore>();
        SetScore? current = null;
        if (!team)
        {
            foreach (var pair in left.At("Splits").Items().Zip(right.At("Splits").Items()))
            {
                if (pair.First.At("Res").Text().Length == 0 || pair.Second.At("Res").Text().Length == 0)
                    continue;
                var set = new SetScore(pair.First.At("Res").Number(), pair.Second.At("Res").Number());
                if (Math.Max(set.Left, set.Right) >= 11 && Math.Abs(set.Left - set.Right) >= 2)
                    completed.Add(set);
                else { current = set; break; }
            }
        }
        if (status != MatchStatus.Live) current = null;
        var known = left.At("Result").Text().Length > 0 && right.At("Result").Text().Length > 0;
        var a = left.At("Result").Number();
        var b = right.At("Result").Number();
        var reconciled = false;
        if (status != MatchStatus.Upcoming && !team && completed.Count > a + b)
        {
            a = completed.Count(s => s.Left > s.Right);
            b = completed.Count(s => s.Right > s.Left);
            known = reconciled = true;
        }
        return new Match($"asiangames:{key}", "majors",
            $"2026 爱知·名古屋亚运会 · {eventName} · {row.At("PhaseDescA").Text()}", status,
            start.ToLocalTime(), names[0], names[1])
        {
            PlayerARaw = left.At("Name").Text(), PlayerBRaw = right.At("Name").Text(),
            PlayerACountryCode = left.At("Org").Text(),
            PlayerBCountryCode = right.At("Org").Text(),
            ScoreA = a, ScoreB = b, ScoreKnown = known, Sets = completed,
            CurrentSet = current, ScoreReconciled = reconciled
        };
    }

    private static string CountryName(JsonElement side) => side.At("Org").Text() switch
    {
        "CHN" => "中国", "JPN" => "日本", "KOR" => "韩国", "PRK" => "朝鲜",
        "HKG" => "中国香港", "MAC" => "中国澳门", "TPE" => "中国台北",
        "IND" => "印度", "SGP" => "新加坡", "THA" => "泰国", "MAS" => "马来西亚",
        "VIE" => "越南", "KAZ" => "哈萨克斯坦", "IRI" => "伊朗",
        _ => side.At("Name").Text()
    };

    public void Dispose() => _http.Dispose();
}
