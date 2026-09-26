using TableTennisLive.Core.Models;

namespace TableTennisLive.Core.Services;

public sealed class MatchAlertTracker
{
    private readonly Dictionary<string, Match> _previous = [];
    private readonly HashSet<string> _startSent = [];
    private readonly HashSet<string> _finalSent = [];

    public IReadOnlyList<MatchAlert> Update(Match match, bool favorite,
        Func<string, bool> enabled)
    {
        if (!favorite) { _previous.Remove(match.Id); return []; }
        if (match.DataStale) return [];
        _previous.TryGetValue(match.Id, out var old);
        _previous[match.Id] = match;
        if (old is null) return [];
        var label = $"{match.PlayerA} vs {match.PlayerB}";
        var alerts = new List<MatchAlert>();
        if (old.Status == MatchStatus.Upcoming && match.Status == MatchStatus.Live)
        {
            if (_startSent.Add(match.Id) && enabled("start"))
                alerts.Add(new(match.Id, "start", "关注的比赛已开始", label));
        }
        else if (old.Status == MatchStatus.Live && match.Status == MatchStatus.Live &&
                 match.ScoreKnown && old.ScoreKnown && enabled("score") &&
                 (match.ScoreA != old.ScoreA || match.ScoreB != old.ScoreB))
            alerts.Add(new(match.Id, "score", "关注的比赛大比分变化",
                $"{label}  {match.ScoreA}:{match.ScoreB}"));
        if (old.Status != MatchStatus.Finished && match.Status == MatchStatus.Finished &&
            _finalSent.Add(match.Id) && enabled("final"))
            alerts.Add(new(match.Id, "final", "关注的比赛已结束",
                label + (match.ScoreKnown ? $"  {match.ScoreA}:{match.ScoreB}" : "")));
        return alerts;
    }

    public MatchAlert? Due(Match match, DateTimeOffset now, Func<string, bool> enabled)
    {
        if (!enabled("start") || match.DataStale || match.Status != MatchStatus.Upcoming ||
            _startSent.Contains(match.Id)) return null;
        var remaining = match.StartTime - now;
        if (remaining < TimeSpan.Zero || remaining > TimeSpan.FromMinutes(5)) return null;
        _startSent.Add(match.Id);
        return new(match.Id, "start", "关注的比赛即将开始",
            $"{match.PlayerA} vs {match.PlayerB} · {match.StartTime:HH:mm}");
    }

    public void Forget(string id)
    {
        _previous.Remove(id);
        _startSent.Remove(id);
        _finalSent.Remove(id);
    }
}
