namespace TableTennisLive.Core.Models;

public sealed record PlayerProfile(string Id, string Name, string CountryCode,
    string CountryName, int? Rank, int? Points, int? Age, string Hand,
    int? WinRate, Uri? Portrait, string Biography, Uri? OfficialPage)
{
    public int? YearWins { get; init; }
    public int? YearMatches { get; init; }
}
