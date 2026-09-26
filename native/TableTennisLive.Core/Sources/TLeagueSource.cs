using System.Net;
using System.Text.RegularExpressions;
using TableTennisLive.Core.Models;
using TableTennisLive.Core.Services;
using ScoreMatch = TableTennisLive.Core.Models.Match;

namespace TableTennisLive.Core.Sources;

/// <summary>Japan T.League schedule and completed match details. Never reports LIVE.</summary>
public sealed class TLeagueSource : IMatchSource, IDisposable
{
    private readonly HttpClient _http = new(new HttpClientHandler { AutomaticDecompression =
        DecompressionMethods.GZip | DecompressionMethods.Deflate | DecompressionMethods.Brotli })
    { Timeout = TimeSpan.FromSeconds(15) };
    private readonly Dictionary<string, (DateTimeOffset Time, IReadOnlyList<TeamGame> Games)> _details = [];
    private IReadOnlyList<ScheduleRow> _rows = [];
    private DateTimeOffset _rowsAt = DateTimeOffset.MinValue;
    public string Name => "T.League";

    public TLeagueSource() => _http.DefaultRequestHeaders.UserAgent.ParseAdd("Mozilla/5.0");

    public async Task<IReadOnlyList<ScoreMatch>> GetMatchesAsync(CancellationToken ct)
    {
        if (DateTimeOffset.UtcNow - _rowsAt >= TimeSpan.FromSeconds(10))
        {
            var html = await _http.GetStringAsync("https://tleague.jp/schedule/", ct).ConfigureAwait(false);
            _rows = ParseScheduleHtml(html);
            _rowsAt = DateTimeOffset.UtcNow;
        }
        var output = _rows.Select(ToMatch).OfType<ScoreMatch>().ToList();
        foreach (var match in output.Where(m => m.Status == MatchStatus.Finished)
                     .OrderByDescending(m => m.StartTime).Take(6).ToArray())
        {
            if (match.Id.StartsWith("tleague:time-")) continue;
            var games = await DetailGamesAsync(match.Id["tleague:".Length..], ct).ConfigureAwait(false);
            var index = output.FindIndex(m => m.Id == match.Id);
            output[index] = match with { Games = games };
        }
        return output;
    }

    public async Task<ScoreMatch?> GetDetailAsync(string matchId, CancellationToken ct)
    {
        var row = _rows.FirstOrDefault(r => "tleague:" + r.Id == matchId);
        var match = row is null ? null : ToMatch(row);
        return match is null || row!.Id.StartsWith("time-") ? match
            : match with { Games = await DetailGamesAsync(row.Id, ct).ConfigureAwait(false) };
    }

    private async Task<IReadOnlyList<TeamGame>> DetailGamesAsync(string id, CancellationToken ct)
    {
        if (_details.TryGetValue(id, out var cached) && DateTimeOffset.UtcNow - cached.Time < TimeSpan.FromHours(1))
            return cached.Games;
        try
        {
            var html = await _http.GetStringAsync($"https://tleague.jp/schedule/detail.php?id={Uri.EscapeDataString(id)}", ct)
                .ConfigureAwait(false);
            var games = ParseDetailHtml(html);
            _details[id] = (DateTimeOffset.UtcNow, games);
            return games;
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
        catch { return []; }
    }

    public sealed record ScheduleRow(string Id, DateTimeOffset Start, string Gender,
        string Home, string Away, int? ScoreA, int? ScoreB);

    public static IReadOnlyList<ScheduleRow> ParseScheduleHtml(string html)
    {
        var rows = new List<ScheduleRow>();
        foreach (var raw in Regex.Split(html, @"<tr\b", RegexOptions.IgnoreCase))
        {
            var row = raw.Split("</tr>", 2)[0];
            var date = Regex.Match(row, @"(\d{4})年\s*(\d{1,2})月(\d{1,2})日\([^)]*\)\s*(\d{1,2}):(\d{2})");
            if (!date.Success) continue;
            DateTimeOffset start;
            try
            {
                start = new DateTimeOffset(int.Parse(date.Groups[1].Value), int.Parse(date.Groups[2].Value),
                    int.Parse(date.Groups[3].Value), int.Parse(date.Groups[4].Value),
                    int.Parse(date.Groups[5].Value), 0, TimeSpan.FromHours(9)).ToLocalTime();
            }
            catch (ArgumentOutOfRangeException) { continue; }
            var teams = Regex.Matches(row, "<span class=\"d-none d-lg-inline\">([^<]+)</span>")
                .Select(m => WebUtility.HtmlDecode(m.Groups[1].Value.Trim())).Take(2).ToArray();
            if (teams.Length < 2) continue;
            var gender = Regex.Match(row, @">(男子|女子)<");
            var score = Regex.Match(row, @"<b[^>]*>\s*<span[^>]*>(\d+)</span>\s*[-－]\s*<span[^>]*>(\d+)</span>\s*</b>", RegexOptions.Singleline);
            var detail = Regex.Match(row, @"detail\.php\?id=(\d+)");
            var id = detail.Success ? detail.Groups[1].Value : $"time-{start:yyyyMMddHHmm}";
            rows.Add(new(id, start, gender.Success ? gender.Groups[1].Value : "",
                teams[0], teams[1], score.Success ? int.Parse(score.Groups[1].Value) : null,
                score.Success ? int.Parse(score.Groups[2].Value) : null));
        }
        return rows;
    }

    public static IReadOnlyList<TeamGame> ParseDetailHtml(string html)
    {
        var games = new List<TeamGame>();
        foreach (var part in Regex.Split(html, @"第\d+マッチ").Skip(1))
        {
            var block = part.Split("<h2", 2)[0];
            var playerBlocks = Regex.Matches(block, "<div class=\"text-center py-4\">(.*?)</div>", RegexOptions.Singleline)
                .Take(2).Select(m => m.Groups[1].Value).ToArray();
            if (playerBlocks.Length < 2) continue;
            static string Players(string text) => string.Join(" / ",
                Regex.Matches(text, @"/player/detail\.php\?player=\d+[^>]*>([^<]+)</a>")
                    .Select(m => WebUtility.HtmlDecode(m.Groups[1].Value.Trim())));
            var left = Players(playerBlocks[0]);
            var right = Players(playerBlocks[1]);
            if (left.Length == 0 || right.Length == 0) continue;
            var sets = Regex.Matches(block, "<div class=\"text-center\">\\s*(\\d+)\\s*-\\s*(\\d+)\\s*</div>")
                .Select(m => new SetScore(int.Parse(m.Groups[1].Value), int.Parse(m.Groups[2].Value)))
                .ToArray();
            if (sets.Length == 0) continue;
            games.Add(new(left, right, sets.Count(s => s.Left > s.Right),
                sets.Count(s => s.Right > s.Left), sets));
        }
        return games;
    }

    private static ScoreMatch? ToMatch(ScheduleRow row)
    {
        if (row.ScoreA is null && row.Start > DateTimeOffset.Now.AddDays(7)) return null;
        var finished = row.ScoreA is not null && row.ScoreB is not null;
        return new ScoreMatch("tleague:" + row.Id, "T.League",
            "日本 T.League" + (row.Gender.Length > 0 ? " · " + row.Gender : ""),
            finished ? MatchStatus.Finished : MatchStatus.Upcoming, row.Start, row.Home, row.Away)
        {
            PlayerARaw = row.Home, PlayerBRaw = row.Away,
            ScoreA = row.ScoreA ?? 0, ScoreB = row.ScoreB ?? 0,
            ScoreKnown = finished
        };
    }

    public void Dispose() => _http.Dispose();
}
