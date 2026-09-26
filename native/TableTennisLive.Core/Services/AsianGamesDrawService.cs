using System.Text.Json;
using System.Text.RegularExpressions;
using TableTennisLive.Core.Models;
using TableTennisLive.Core.Sources;

namespace TableTennisLive.Core.Services;

public sealed class AsianGamesDrawService : IDisposable
{
    private static readonly Dictionary<string, string> Projects = new()
    {
        ["男单"] = "M.SINGLES-----------", ["女单"] = "W.SINGLES-----------",
        ["男双"] = "M.DOUBLES-----------", ["女双"] = "W.DOUBLES-----------",
        ["混双"] = "X.DOUBLES-----------", ["男团"] = "M.TEAM--------------",
        ["女团"] = "W.TEAM--------------"
    };
    private static readonly Dictionary<string, string> RoundNames = new()
    {
        ["R64-"] = "64 强", ["R32-"] = "32 强", ["8FNL"] = "16 强",
        ["QFNL"] = "四分之一决赛", ["SFNL"] = "半决赛", ["FNL-"] = "决赛"
    };
    private readonly AsianGamesSource _source = new();

    public async Task<IReadOnlyList<DrawStage>> GetDrawAsync(string project,
        CancellationToken ct)
    {
        if (!Projects.TryGetValue(project, out var code))
            throw new ArgumentException("不支持的亚运会项目");
        var payload = await _source.GetBracketPayloadAsync(code, ct).ConfigureAwait(false);
        return Parse(payload, code);
    }

    public static IReadOnlyList<DrawStage> Parse(JsonElement payload, string projectCode)
    {
        if (payload.ValueKind != JsonValueKind.Array)
            throw new InvalidDataException("亚运会官方签表格式异常");
        var output = new List<DrawStage>();
        var team = projectCode.Contains(".TEAM");
        foreach (var bracket in payload.Items())
        {
            var rounds = new List<DrawRound>();
            foreach (var phase in bracket.At("Phases").Items())
            {
                var code = phase.At("Code").Text();
                var suffix = code.Split('.').LastOrDefault() ?? code;
                var title = RoundNames.GetValueOrDefault(suffix, phase.At("Desc").Text());
                var matches = new List<DrawMatch>();
                var rows = phase.At("Matches").Items().ToArray();
                var previous = rounds.LastOrDefault()?.Matches ?? [];
                var canLink = previous.Count == rows.Length * 2;
                for (var index = 0; index < rows.Length; index++)
                {
                    var row = rows[index];
                    var info = row.At("Info");
                    var home = row.At("Home");
                    var away = row.At("Away");
                    var leftParent = canLink ? previous[2 * index] : null;
                    var rightParent = canLink ? previous[2 * index + 1] : null;
                    var left = LinkPlayer(Player(home, team), leftParent);
                    var right = LinkPlayer(Player(away, team), rightParent);
                    var bye = info.At("IsBye").Flag();
                    if (bye)
                    {
                        left = left with { Score = "—" };
                        right = right with { Score = "—" };
                    }
                    var detail = info.At("Extensions").Items()
                        .FirstOrDefault(x => x.At("Code").Text() == "ResultDetailWinner")
                        .At("Value").Text();
                    var sets = Regex.Matches(detail, @"(\d+)\s*:\s*(\d+)")
                        .Select(match =>
                        {
                            var a = int.Parse(match.Groups[1].Value);
                            var b = int.Parse(match.Groups[2].Value);
                            return away.At("Win").Flag() && !home.At("Win").Flag()
                                ? new SetScore(b, a) : new SetScore(a, b);
                        }).ToList();
                    while (sets.Count > 0 && sets[^1] == new SetScore(0, 0))
                        sets.RemoveAt(sets.Count - 1);
                    var date = info.At("DateTimeRaw").Text();
                    matches.Add(new(info.At("Key").Text(), matches.Count + 1, left, right,
                        date.Length >= 10 ? date[..10] : "",
                        date.Length >= 16 ? date[11..16] + " JST" : "", sets, bye));
                }
                if (matches.Count > 0) rounds.Add(new(code, title, matches));
            }
            if (rounds.Count > 0)
            {
                var stage = bracket.At("Code").Text();
                output.Add(new(stage == "MAINDRAW" ? "MAIN" : stage, rounds));
            }
        }
        return output;
    }

    private static DrawPlayer Player(JsonElement side, bool team)
    {
        var org = side.At("Org").Text();
        var raw = side.At("Name").Text().Trim();
        var name = org == "BYE" ? "轮空" : raw.Length == 0 ? "待定" :
            team ? org switch
            {
                "CHN" => "中国", "JPN" => "日本", "KOR" => "韩国",
                "HKG" => "中国香港", "TPE" => "中国台北", "IND" => "印度",
                _ => raw
            } : ChineseNames.Display(raw);
        var score = side.At("Res").Text();
        return new(name, raw.Length == 0 ? name : raw, org,
            score.Length == 0 ? "—" : score, side.At("Win").Flag(), "", "")
        { Registration = side.At("Reg").Text() };
    }

    private static DrawPlayer LinkPlayer(DrawPlayer player, DrawMatch? parent)
    {
        if (parent is null || parent.Id.Length == 0) return player;
        if (player.Registration.Length > 0 && player.Name is not ("轮空" or "待定"))
        {
            var declaredWinners = new[] { parent.Left, parent.Right }
                .Where(candidate => candidate.Winner && candidate.Registration.Length > 0)
                .Select(candidate => candidate.Registration).ToHashSet();
            if (declaredWinners.Count > 0 && !declaredWinners.Contains(player.Registration))
                return player;
        }
        return player with { PreviousMatch = parent.Id };
    }

    public void Dispose() => _source.Dispose();
}
