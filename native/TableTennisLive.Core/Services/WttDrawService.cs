using System.Net;
using System.Text.Json;
using System.Text.RegularExpressions;
using TableTennisLive.Core.Models;

namespace TableTennisLive.Core.Services;

public sealed class WttDrawService : IDisposable
{
    private const string Catalog = "https://wtt-web-frontdoor-cthahjeqhbh6aqe3.a01.azurefd.net/" +
        "websitestaticapifiles/general/wtt_upcoming_only_events_list.json";
    private const string Api = "https://wtt-web-cms-api-prod.azurewebsites.net/api/cms/GetBrackets";
    private static readonly Dictionary<string, string> Projects = new()
    {
        ["男单"] = "MSINGLES", ["女单"] = "WSINGLES", ["男双"] = "MDOUBLES",
        ["女双"] = "WDOUBLES", ["混双"] = "XDOUBLES"
    };
    private static readonly Dictionary<string, string> RoundNames = new()
    {
        ["FNL"] = "决赛", ["SFNL"] = "半决赛", ["QFNL"] = "四分之一决赛",
        ["8FNL"] = "16 强", ["R32"] = "32 强", ["R64"] = "64 强",
        ["R128"] = "128 强", ["RND1"] = "资格赛第 1 轮",
        ["RND2"] = "资格赛第 2 轮", ["RND3"] = "资格赛第 3 轮",
        ["RND4"] = "资格赛第 4 轮"
    };
    private readonly OfficialJson _json = new();
    private readonly HttpClient _http = new(new HttpClientHandler
    {
        AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate
    }) { Timeout = TimeSpan.FromSeconds(20) };

    public async Task<IReadOnlyList<DrawEvent>> GetEventsAsync(CancellationToken ct)
    {
        var payload = await _json.GetAsync(Catalog, "draw-events", TimeSpan.FromMinutes(5), ct);
        var now = DateTimeOffset.Now;
        return payload.Items().Select(row =>
        {
            var hasStart = DateTimeOffset.TryParse(row.At("startDateTime").Text(), out var start);
            var hasEnd = DateTimeOffset.TryParse(row.At("endDateTime").Text(), out var end);
            var valid = hasStart && hasEnd;
            return (valid, Item: new DrawEvent(row.At("eventId").Number(),
                row.At("eventName").Text(), start, end));
        }).Where(x => x.valid && x.Item.Id > 0 && MainEvent(x.Item.Name) &&
            x.Item.End >= now.AddDays(-90) && x.Item.Start <= now.AddDays(60))
            .OrderBy(x => x.Item.Start <= now && x.Item.End >= now ? 0 : 1)
            .ThenBy(x => Math.Abs((x.Item.Start - now).TotalDays))
            .Select(x => x.Item).ToArray();
    }

    private static bool MainEvent(string name)
    {
        var lower = name.ToLowerInvariant();
        return !lower.Contains("youth smash") &&
            (lower.Contains("smash") || lower.Contains("wtt champions") ||
             lower.Contains("wtt star contender") || lower.Contains("wtt contender") ||
             lower.StartsWith("wtt ") && lower.Contains("finals"));
    }

    public async Task<IReadOnlyList<DrawStage>> GetDrawAsync(int eventId, string project,
        CancellationToken ct)
    {
        if (eventId <= 0 || !Projects.TryGetValue(project, out var code))
            throw new ArgumentException("不支持的 WTT 赛事或项目");
        var documentCode = "TTE" + code + new string('-', 31);
        using var response = await _http.GetAsync($"{Api}/{eventId}/{documentCode}?q=" +
            DateTimeOffset.UtcNow.ToUnixTimeSeconds() / 30, ct).ConfigureAwait(false);
        if (response.StatusCode == HttpStatusCode.NoContent) return [];
        response.EnsureSuccessStatusCode();
        using var stream = await response.Content.ReadAsStreamAsync(ct).ConfigureAwait(false);
        using var document = await JsonDocument.ParseAsync(stream, cancellationToken: ct)
            .ConfigureAwait(false);
        return Parse(document.RootElement);
    }

    public static IReadOnlyList<DrawStage> Parse(JsonElement payload)
    {
        if (payload.ValueKind is JsonValueKind.Null or JsonValueKind.Undefined) return [];
        var competition = payload.At("Competition");
        if (competition.ValueKind != JsonValueKind.Object)
            throw new InvalidDataException("官方签表格式暂不支持");
        var output = new List<DrawStage>();
        foreach (var bracket in AsList(competition.At("Bracket")))
        {
            var rounds = new List<DrawRound>();
            foreach (var group in AsList(bracket.At("BracketItems")))
            {
                var rows = new List<DrawMatch>();
                foreach (var item in AsList(group.At("BracketItem")))
                {
                    var places = AsList(item.At("CompetitorPlace"))
                        .OrderBy(p => p.At("Pos").Number()).Take(2).ToArray();
                    if (places.Length != 2) continue;
                    var left = Player(places[0]);
                    var right = Player(places[1]);
                    var bye = places.Any(p => p.At("Code").Text() == "BYE");
                    if (bye)
                    {
                        left = left with { Score = "—" };
                        right = right with { Score = "—" };
                    }
                    var detail = item.At("Result").Text();
                    var sets = Regex.Matches(detail, @"(\d+)\s*:\s*(\d+)")
                        .Select(m => new SetScore(int.Parse(m.Groups[1].Value),
                            int.Parse(m.Groups[2].Value))).ToList();
                    while (sets.Count > 0 && sets[^1] == new SetScore(0, 0)) sets.RemoveAt(sets.Count - 1);
                    var id = item.At("Code").Text();
                    if (id.Length == 0) id = item.At("Unit").Text();
                    var order = item.At("Order").Number();
                    if (order == 0) order = item.At("Position").Number();
                    if (order == 0) order = rows.Count + 1;
                    rows.Add(new(id.TrimEnd('-'), order, left, right,
                        item.At("Date").Text(), item.At("Time").Text(), sets, bye));
                }
                if (rows.Count == 0) continue;
                var code = group.At("Code").Text().TrimEnd('-');
                rounds.Add(new(code, RoundNames.GetValueOrDefault(code, code),
                    rows.OrderBy(row => row.Order).ToArray()));
            }
            if (rounds.Count == 0) continue;
            var remaining = rounds.ToList();
            var ordered = new List<DrawRound>();
            while (remaining.Count > 0)
            {
                var active = remaining.SelectMany(round => round.Matches)
                    .Select(match => match.Id).ToHashSet();
                var ready = remaining.Where(round => !round.Matches.Any(match =>
                    new[] { match.Left.PreviousMatch, match.Right.PreviousMatch }
                        .Any(previous => active.Contains(previous) &&
                            !round.Matches.Any(m => m.Id == previous))))
                    .OrderByDescending(round => round.Matches.Count).ThenBy(round => round.Code).ToArray();
                if (ready.Length == 0) throw new InvalidDataException("签表晋级关系存在循环");
                foreach (var round in ready) { ordered.Add(round); remaining.Remove(round); }
            }
            output.Add(new(bracket.At("Code").Text(), ordered));
        }
        return output;
    }

    private static IReadOnlyList<JsonElement> AsList(JsonElement value) => value.ValueKind switch
    {
        JsonValueKind.Array => value.Items().ToArray(),
        JsonValueKind.Object => [value],
        _ => []
    };

    private static DrawPlayer Player(JsonElement place)
    {
        var competitor = place.At("Competitor");
        var raw = competitor.At("Description").At("TeamName").Text();
        if (raw.Length == 0) raw = place.At("Code").Text();
        var name = place.At("Code").Text() switch
        {
            "BYE" => "轮空", "TBD" => "待定", _ => ChineseNames.Display(raw)
        };
        var athletes = AsList(competitor.At("Composition").At("Athlete"));
        var playerId = athletes.Count == 1 ? athletes[0].At("Code").Text() :
            athletes.Count == 0 && competitor.At("Type").Text() == "A"
                ? competitor.At("Code").Text() : "";
        if (!System.Text.RegularExpressions.Regex.IsMatch(playerId, @"^[1-9]\d*$")) playerId = "";
        var score = place.At("Result").Text();
        return new(name, raw, competitor.At("Organization").Text(),
            score.Length == 0 ? "—" : score, place.At("Wlt").Text() == "W",
            place.At("PreviousUnit").At("Unit").Text().TrimEnd('-'), playerId);
    }

    public void Dispose() { _http.Dispose(); _json.Dispose(); }
}
