using TableTennisLive.Core.Models;

namespace TableTennisLive.Core.Services;

public interface IMatchSource
{
    string Name { get; }
    Task<IReadOnlyList<Match>> GetMatchesAsync(CancellationToken cancellationToken);
    Task<Match?> GetDetailAsync(string matchId, CancellationToken cancellationToken);
}

public sealed record SourceHealth(string Name, DateTimeOffset? LastSuccess,
    string? Error, bool Stale);
