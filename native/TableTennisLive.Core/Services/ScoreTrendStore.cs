using TableTennisLive.Core.Models;

namespace TableTennisLive.Core.Services;

/// <summary>Observed scores only. No point-by-point interpolation or invented rallies.</summary>
public sealed class ScoreTrendStore
{
    private sealed record Observation(int A, int B, bool Final, HashSet<string> Events);
    private readonly Dictionary<string, Dictionary<int, SortedDictionary<int, Observation>>> _series = [];
    private const int MaxMatches = 128;
    private const int MaxPointsPerSet = 250;

    public void Observe(Match match)
    {
        if (match.Status == MatchStatus.Upcoming || match.DataStale || match.HasGames ||
            (match.Sets.Count == 0 && match.CurrentSet is null && match.ScoreEvents.Count == 0))
            return;
        if (!_series.ContainsKey(match.Id) && _series.Count >= MaxMatches)
            _series.Remove(_series.Keys.First());
        if (!_series.TryGetValue(match.Id, out var sets))
            _series[match.Id] = sets = [];
        foreach (var scoreEvent in match.ScoreEvents)
        {
            if (scoreEvent.SetNumber < 1 || scoreEvent.ScoreA < 0 || scoreEvent.ScoreB < 0)
                continue;
            var point = Put(sets, scoreEvent.SetNumber, scoreEvent.ScoreA, scoreEvent.ScoreB);
            if (point is not null && scoreEvent.Kind is "point" or "timeout" or "match_point")
                point.Events.Add(scoreEvent.Kind);
        }
        for (var index = 0; index < match.Sets.Count; index++)
        {
            var set = match.Sets[index];
            if (set.Left == 0 && set.Right == 0) continue;
            var point = Put(sets, index + 1, set.Left, set.Right);
            if (point is not null) sets[index + 1][set.Left + set.Right] = point with { Final = true };
        }
        if (match.CurrentSet is { } current)
            Put(sets, match.Sets.Count + 1, current.Left, current.Right);
    }

    private static Observation? Put(Dictionary<int, SortedDictionary<int, Observation>> sets,
        int number, int a, int b)
    {
        if (!sets.TryGetValue(number, out var points)) sets[number] = points = [];
        var progress = a + b;
        if (points.TryGetValue(progress, out var previous) &&
            (previous.A != a || previous.B != b))
            points.Clear(); // An official correction invalidates the contradictory path.
        if (!points.ContainsKey(progress) && points.Count >= MaxPointsPerSet) return null;
        if (!points.TryGetValue(progress, out var value))
            points[progress] = value = new(a, b, false, []);
        return value;
    }

    public IReadOnlyList<TrendPoint> Points(string matchId)
    {
        if (!_series.TryGetValue(matchId, out var sets)) return [];
        return sets.OrderBy(set => set.Key)
            .SelectMany(set => set.Value.Values.Select(point => new TrendPoint(set.Key,
                point.A, point.B, point.Final, point.Events.Order().ToArray())))
            .ToArray();
    }
}
