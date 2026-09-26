namespace TableTennisLive.Core.Models;

public sealed record MatchAlert(string MatchId, string Kind, string Title, string Message);
