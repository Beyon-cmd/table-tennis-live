using System.Reflection;
using System.Text.Json;
using TableTennisLive.Core.Models;

namespace TableTennisLive.Core.Services;

/// <summary>Verified final-result archive, never a substitute for current LIVE fixtures.</summary>
public static class HistoricalMajorArchive
{
    public static IReadOnlyList<Match> Load()
    {
        var assembly = typeof(HistoricalMajorArchive).Assembly;
        var resource = assembly.GetManifestResourceNames().Single(x => x.EndsWith("historical-majors.json"));
        using var stream = assembly.GetManifestResourceStream(resource)!;
        using var doc = JsonDocument.Parse(stream);
        var root = doc.RootElement;
        var teams = root.At("teams");
        var result = new List<Match>();
        foreach (var tournament in root.At("events").Items())
        {
            var eventId = tournament.At("id").Number();
            var category = tournament.At("type").Text();
            var eventDate = DateTimeOffset.Parse(tournament.At("start").Text());
            foreach (var final in tournament.At("finals").Items())
            {
                var parts = final.Items().ToArray();
                if (parts.Length != 5) continue;
                var discipline = parts[0].Text();
                var champion = parts[1].Items().ToArray();
                var runner = parts[2].Items().ToArray();
                if (champion.Length < 2 || runner.Length < 2) continue;
                var score = parts[3].Items().ToArray();
                var setScores = parts[4].Items().Select(s => s.Items().ToArray())
                    .Where(s => s.Length == 2)
                    .Select(s => new SetScore(s[0].Number(), s[1].Number())).ToArray();
                var team = teams.At($"{eventId}|{discipline}");
                var teamParts = team.Items().ToArray();
                var games = teamParts.Length == 3
                    ? teamParts[2].Items().Select(Game).ToArray()
                    : [];
                var start = teamParts.Length == 3 && DateTimeOffset.TryParse(teamParts[0].Text(), out var exact)
                    ? exact : eventDate;
                var eventName = tournament.At("name_zh").Text();
                var city = tournament.At("city").Text();
                var year = tournament.At("year").Number();
                result.Add(new Match($"major:{eventId}:{discipline}", "historical",
                    $"{year} {eventName} · {city} · {discipline}", MatchStatus.Finished,
                    start, champion[0].Text(), runner[0].Text())
                {
                    PlayerARaw = champion[1].Text(), PlayerBRaw = runner[1].Text(),
                    ScoreA = score.Length == 2 ? score[0].Number() : 0,
                    ScoreB = score.Length == 2 ? score[1].Number() : 0,
                    ScoreKnown = score.Length == 2, Sets = setScores, Games = games,
                    MajorCategory = category, LastUpdate = tournament.At("end").Text() is var date &&
                        DateTimeOffset.TryParse(date, out var ended) ? ended : start
                });
            }
        }
        return result;
    }

    private static TeamGame Game(JsonElement row)
    {
        var fields = row.Items().ToArray();
        if (fields.Length != 5) throw new InvalidDataException("Invalid verified team game");
        var sets = fields[4].Items().Select(s => s.Items().ToArray())
            .Where(s => s.Length == 2).Select(s => new SetScore(s[0].Number(), s[1].Number()))
            .ToArray();
        return new(fields[0].Text(), fields[1].Text(), fields[2].Number(), fields[3].Number(), sets);
    }
}
