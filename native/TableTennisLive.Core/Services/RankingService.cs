using System.Text.Json;
using TableTennisLive.Core.Models;

namespace TableTennisLive.Core.Services;

public sealed class RankingService : IDisposable
{
    private const string BaseUrl = "https://wtt-web-frontdoor-cthahjeqhbh6aqe3.a01.azurefd.net/ranking/";
    private static readonly (string File, string Category, bool Pairs)[] Feeds =
    [
        ("SEN_SINGLES", "SEN", false), ("SEN_DOUBLES", "SEN", true),
        ("YOU_SINGLES", "YOU", false), ("YOU_DOUBLES", "YOU", true)
    ];
    private readonly OfficialJson _json = new();
    private readonly string _cachePath = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "TableTennisLive", "ranking-cache.json");
    private IReadOnlyList<RankingEntry> _current = [];
    private DateTimeOffset _lastFetch = DateTimeOffset.MinValue;

    public IReadOnlyList<RankingEntry> LoadCached()
    {
        try
        {
            _current = JsonSerializer.Deserialize<List<RankingEntry>>(File.ReadAllText(_cachePath)) ?? [];
        }
        catch (Exception ex) when (ex is IOException or JsonException or UnauthorizedAccessException)
        {
            _current = [];
        }
        return _current;
    }

    public async Task<IReadOnlyList<RankingEntry>> RefreshAsync(CancellationToken ct)
    {
        if (_current.Count > 0 && DateTimeOffset.UtcNow - _lastFetch < TimeSpan.FromSeconds(60))
            return _current;
        try
        {
            var previous = _current;
            var feeds = await Task.WhenAll(Feeds.Select(async feed =>
            {
                try
                {
                    var payload = await _json.GetAsync(BaseUrl + feed.File + ".json",
                        "rankings-" + feed.File, TimeSpan.FromSeconds(60), ct);
                    return feed.Pairs ? ParsePairs(payload, feed.Category) :
                        ParseSingles(payload, feed.Category);
                }
                catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
                catch
                {
                    return previous.Where(row => row.CategoryCode == feed.Category &&
                        row.IsPair == feed.Pairs).ToArray();
                }
            }));
            var rows = feeds.SelectMany(feed => feed).ToArray();
            if (!rows.Any(r => r.CategoryCode == "SEN" && r.EventCode == "MS") ||
                !rows.Any(r => r.CategoryCode == "SEN" && r.EventCode == "WS"))
                throw new InvalidDataException("WTT 官方男单或女单排名不完整");
            _current = rows;
            _lastFetch = DateTimeOffset.UtcNow;
            Directory.CreateDirectory(Path.GetDirectoryName(_cachePath)!);
            var temporary = _cachePath + ".tmp";
            await File.WriteAllTextAsync(temporary, JsonSerializer.Serialize(rows), ct);
            File.Move(temporary, _cachePath, overwrite: true);
            return rows;
        }
        catch (OperationCanceledException) when (ct.IsCancellationRequested) { throw; }
        catch when (_current.Count > 0) { return _current; }
    }

    public static IReadOnlyList<RankingEntry> Parse(JsonElement payload) =>
        ParseSingles(payload, "SEN");

    public static IReadOnlyList<RankingEntry> ParseSingles(JsonElement payload, string category)
    {
        var result = new List<RankingEntry>();
        foreach (var row in payload.At("Result").Items())
        {
            var eventCode = row.At("SubEventCode").Text();
            if (eventCode is not ("MS" or "WS" or "MDI" or "WDI" or "XDI")) continue;
            var rank = row.At("CurrentRank").Number();
            var points = row.At("RankingPointsYTD").Number();
            var name = row.At("PlayerName").Text();
            if (rank <= 0 || rank > 100 || name.Length == 0) continue;
            DateTimeOffset? published = DateTimeOffset.TryParse(row.At("PublishDate").Text(),
                out var date) ? date : null;
            result.Add(new(eventCode, rank, name, row.At("CountryCode").Text(),
                points, row.At("RankingDifference").Number(), row.At("IttfId").Text(), published)
            {
                CategoryCode = category, AgeCategoryCode = row.At("AgeCategoryCode").Text()
            });
        }
        return result.OrderBy(r => r.EventCode).ThenBy(r => r.Rank)
            .ThenBy(r => r.PlayerName).ToArray();
    }

    public static IReadOnlyList<RankingEntry> ParsePairs(JsonElement payload, string category)
    {
        var result = new List<RankingEntry>();
        foreach (var row in payload.At("Result").Items())
        {
            var code = row.At("SubEventCode").Text();
            if (code is not ("MD" or "WD" or "XD")) continue;
            var rank = row.At("CurrentRank").Number();
            var first = row.At("PlayerName1").Text();
            var second = row.At("PlayerName1d").Text();
            if (rank <= 0 || rank > 100 || first.Length == 0 || second.Length == 0) continue;
            DateTimeOffset? published = DateTimeOffset.TryParse(row.At("PublishDate").Text(),
                out var date) ? date : null;
            result.Add(new(code, rank, first, row.At("CountryCode1").Text(),
                row.At("Points").Number(), row.At("RankingDifference").Number(),
                row.At("IttfId1").Text(), published)
            {
                CategoryCode = category, AgeCategoryCode = row.At("AgeCategoryCode").Text(),
                PartnerName = second, PartnerId = row.At("IttfId1d").Text(),
                PartnerCountryCode = row.At("CountryCode1d").Text(),
                PairId = row.At("PairId").Text()
            });
        }
        return result.OrderBy(r => r.EventCode).ThenBy(r => r.Rank)
            .ThenBy(r => r.DisplayName).ToArray();
    }

    public void Dispose() => _json.Dispose();
}
