namespace TableTennisLive.Core.Models;

public enum MatchStatus { Upcoming, Live, Finished }

public sealed record SetScore(int Left, int Right);

public sealed record TeamGame(string PlayerA, string PlayerB, int ScoreA, int ScoreB,
    IReadOnlyList<SetScore> Sets);

public sealed record ScoreEvent(int SetNumber, int ScoreA, int ScoreB, string Kind,
    int? Player = null);

public sealed record Match(
    string Id,
    string Source,
    string Competition,
    MatchStatus Status,
    DateTimeOffset StartTime,
    string PlayerA,
    string PlayerB)
{
    public string PlayerARaw { get; init; } = "";
    public string PlayerBRaw { get; init; } = "";
    public string PlayerAId { get; init; } = "";
    public string PlayerBId { get; init; } = "";
    public string PlayerACountryCode { get; init; } = "";
    public string PlayerBCountryCode { get; init; } = "";
    public int ScoreA { get; init; }
    public int ScoreB { get; init; }
    public bool ScoreKnown { get; init; }
    public IReadOnlyList<SetScore> Sets { get; init; } = [];
    public SetScore? CurrentSet { get; init; }
    public IReadOnlyList<TeamGame> Games { get; init; } = [];
    public IReadOnlyList<ScoreEvent> ScoreEvents { get; init; } = [];
    public int? WinningSets { get; init; }
    public bool ScoreReconciled { get; init; }
    public bool DataStale { get; init; }
    public string MajorCategory { get; init; } = "";
    public DateTimeOffset LastUpdate { get; init; } = DateTimeOffset.Now;

    public bool HasScore => ScoreKnown && (Sets.Count > 0 || ScoreA > 0 || ScoreB > 0);
    public bool HasGames => Games.Count > 0;

    public string SearchText => string.Join(' ', new[] { PlayerA, PlayerB, PlayerARaw,
        PlayerBRaw, Competition, Source }.Concat(Games.SelectMany(g => new[] { g.PlayerA, g.PlayerB })))
        .ToLowerInvariant();

    // Deliberately excludes LastUpdate: a network poll alone must not redraw a card.
    public string ContentFingerprint() => System.Text.Json.JsonSerializer.Serialize(new
    {
        Id, Source, Competition, Status, StartTime, PlayerA, PlayerB,
        PlayerARaw, PlayerBRaw, PlayerAId, PlayerBId, PlayerACountryCode,
        PlayerBCountryCode, ScoreA, ScoreB,
        ScoreKnown, Sets, CurrentSet, Games, ScoreEvents, WinningSets,
        ScoreReconciled, DataStale, MajorCategory
    });
}
