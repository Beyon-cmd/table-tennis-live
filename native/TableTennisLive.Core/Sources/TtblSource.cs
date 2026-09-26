using System.Net;
using System.Text.Json;
using System.Text.RegularExpressions;
using TableTennisLive.Core.Models;
using TableTennisLive.Core.Services;
using ScoreMatch = TableTennisLive.Core.Models.Match;

namespace TableTennisLive.Core.Sources;

/// <summary>Official German TTBL Next.js schedule and per-game results.</summary>
public sealed class TtblSource : IMatchSource, IDisposable
{
    private const string Base = "https://www.ttbl.de";
    private readonly HttpClient _http = new(new HttpClientHandler { AutomaticDecompression =
        DecompressionMethods.GZip | DecompressionMethods.Deflate | DecompressionMethods.Brotli })
    { Timeout = TimeSpan.FromSeconds(15) };
    private readonly OfficialJson _json = new();
    private string _buildId = "";
    private DateTimeOffset _buildAt = DateTimeOffset.MinValue;
    private JsonElement _homeRows;
    private JsonElement _homeSeason;
    private DateTimeOffset _rowsAt = DateTimeOffset.MinValue;
    private IReadOnlyList<JsonElement> _rows = [];
    private readonly Dictionary<string, (DateTimeOffset Time, IReadOnlyList<TeamGame> Games)> _gamesCache = [];
    public string Name => "TTBL";

    public TtblSource() => _http.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0");

    public async Task<IReadOnlyList<ScoreMatch>> GetMatchesAsync(CancellationToken ct)
    {
        var rows = await ScheduleAsync(ct).ConfigureAwait(false);
        var output = rows.Select(ToMatch).OfType<ScoreMatch>().ToList();
        foreach (var match in output.Where(m => m.Status == MatchStatus.Live)
                     .Concat(output.Where(m => m.Status == MatchStatus.Finished)
                         .OrderByDescending(m => m.StartTime).Take(4)).ToArray())
        {
            var index = output.FindIndex(m => m.Id == match.Id);
            if (index >= 0) output[index] = match with
            { Games = await GamesAsync(match.Id, match.Status, ct).ConfigureAwait(false) };
        }
        return output;
    }

    public async Task<ScoreMatch?> GetDetailAsync(string id, CancellationToken ct)
    {
        var row = _rows.FirstOrDefault(r => "ttbl:" + r.At("id").Text() == id);
        var match = ToMatch(row);
        return match is null ? null : match with
        { Games = await GamesAsync(id, match.Status, ct).ConfigureAwait(false) };
    }

    private async Task<IReadOnlyList<JsonElement>> ScheduleAsync(CancellationToken ct)
    {
        if (DateTimeOffset.UtcNow - _rowsAt < TimeSpan.FromSeconds(2)) return _rows;
        var build = await BuildIdAsync(ct).ConfigureAwait(false);
        var data = await _json.GetAsync($"{Base}/_next/data/{build}/de/bundesliga/gameschedule/current/current/all.json",
            "schedule-" + build, TimeSpan.FromSeconds(2), ct).ConfigureAwait(false);
        var props = data.At("pageProps");
        var redirect = props.At("__N_REDIRECT").Text();
        if (redirect.Length > 0)
        {
            data = await _json.GetAsync($"{Base}/_next/data/{build}{redirect}.json",
                "redirect-" + build, TimeSpan.FromSeconds(2), ct).ConfigureAwait(false);
            props = data.At("pageProps");
        }
        var byId = props.At("matches").Items()
            .Where(row => row.At("id").Text().Length > 0)
            .ToDictionary(row => row.At("id").Text(), row => row);
        foreach (var row in _homeRows.Items())
        {
            var id = row.At("id").Text();
            if (id.Length > 0 && !byId.ContainsKey(id)) byId[id] = row;
        }
        _rows = byId.Values.ToArray();
        _rowsAt = DateTimeOffset.UtcNow;
        return _rows;
    }

    private async Task<string> BuildIdAsync(CancellationToken ct)
    {
        if (_buildId.Length > 0 && DateTimeOffset.UtcNow - _buildAt < TimeSpan.FromHours(1))
            return _buildId;
        var html = await _http.GetStringAsync(Base + "/", ct).ConfigureAwait(false);
        var data = Regex.Match(html, "<script id=\"__NEXT_DATA__\" type=\"application/json\"[^>]*>(.*?)</script>",
            RegexOptions.Singleline);
        if (!data.Success) throw new InvalidDataException("TTBL 首页没有 __NEXT_DATA__");
        using var doc = JsonDocument.Parse(data.Groups[1].Value);
        var root = doc.RootElement;
        _buildId = root.At("buildId").Text();
        if (_buildId.Length == 0) throw new InvalidDataException("TTBL 首页没有 buildId");
        _homeRows = root.At("props").At("pageProps").At("currentMatches").Clone();
        _homeSeason = root.At("props").At("pageProps").At("season").Clone();
        _buildAt = DateTimeOffset.UtcNow;
        return _buildId;
    }

    private async Task<IReadOnlyList<TeamGame>> GamesAsync(string id, MatchStatus status, CancellationToken ct)
    {
        var ttl = status == MatchStatus.Finished ? TimeSpan.FromHours(1) : TimeSpan.FromSeconds(2);
        if (_gamesCache.TryGetValue(id, out var cached) && DateTimeOffset.UtcNow - cached.Time < ttl)
            return cached.Games;
        var row = _rows.FirstOrDefault(r => "ttbl:" + r.At("id").Text() == id);
        var season = row.At("season");
        if (season.ValueKind != JsonValueKind.Object) season = _homeSeason;
        var seasonText = $"{season.At("startYear").Text()}-{season.At("endYear").Text()}";
        var gameday = row.At("gameday").At("index").Text();
        if (seasonText.StartsWith('-') || gameday.Length == 0) return [];
        try
        {
            var build = await BuildIdAsync(ct).ConfigureAwait(false);
            var data = await _json.GetAsync($"{Base}/_next/data/{build}/de/bundesliga/gameday/" +
                $"{seasonText}/{gameday}/{Uri.EscapeDataString(id["ttbl:".Length..])}.json",
                "game-" + id, ttl, ct).ConfigureAwait(false);
            var games = ParseGames(data.At("pageProps").At("selectedMatch"));
            _gamesCache[id] = (DateTimeOffset.UtcNow, games);
            return games;
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
        catch { return []; }
    }

    public static ScoreMatch? ToMatch(JsonElement row)
    {
        var state = row.At("matchState").Text();
        if (state.Length == 0 || state == "Inactive") return null;
        var home = row.At("homeTeam").At("seasonTeam").At("name").Text();
        var away = row.At("awayTeam").At("seasonTeam").At("name").Text();
        if (home.Length == 0 || away.Length == 0 ||
            !long.TryParse(row.At("timeStamp").Text(), out var timestamp)) return null;
        var start = DateTimeOffset.FromUnixTimeSeconds(timestamp).ToLocalTime();
        var a = row.At("homeGames").Number();
        var b = row.At("awayGames").Number();
        var known = a > 0 || b > 0;
        var status = state == "Finished" ? MatchStatus.Finished : known ? MatchStatus.Live
            : start > DateTimeOffset.Now.AddMinutes(-30) ? MatchStatus.Upcoming : (MatchStatus?)null;
        if (status is null) return null;
        var day = row.At("gameday").At("name").Text();
        return new ScoreMatch("ttbl:" + row.At("id").Text(), "TTBL",
            "德国 TTBL · " + (day.Length == 0 ? "Bundesliga" : day), status.Value,
            start, home, away)
        {
            PlayerARaw = home, PlayerBRaw = away,
            ScoreA = a, ScoreB = b, ScoreKnown = known || status == MatchStatus.Finished
        };
    }

    public static IReadOnlyList<TeamGame> ParseGames(JsonElement selected)
    {
        var output = new List<TeamGame>();
        foreach (var game in selected.At("games").Items())
        {
            var home = PlayerName(game.At("homePlayer"), game.At("homeDouble"));
            var away = PlayerName(game.At("awayPlayer"), game.At("awayDouble"));
            if (home.Length == 0 || away.Length == 0) continue;
            var sets = new List<SetScore>();
            for (var number = 1; number <= 5; number++)
            {
                var a = game.At($"set{number}HomeScore");
                var b = game.At($"set{number}AwayScore");
                if (a.ValueKind != JsonValueKind.Undefined && b.ValueKind != JsonValueKind.Undefined &&
                    a.Number() + b.Number() > 0) sets.Add(new(a.Number(), b.Number()));
            }
            if (sets.Count == 0) continue;
            output.Add(new(home, away, game.At("homeSets").Number(), game.At("awaySets").Number(), sets));
        }
        return output;
    }

    private static string PlayerName(JsonElement player, JsonElement doubles)
    {
        static string One(JsonElement element) =>
            (element.At("firstName").Text() + " " + element.At("lastName").Text()).Trim();
        if (player.ValueKind == JsonValueKind.Object) return One(player);
        return doubles.ValueKind == JsonValueKind.Object
            ? string.Join(" / ", new[] { One(doubles.At("leaguePlayerOne")),
                One(doubles.At("leaguePlayerTwo")) }.Where(name => name.Length > 0))
            : "";
    }

    public void Dispose()
    {
        _http.Dispose();
        _json.Dispose();
    }
}
