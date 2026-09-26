namespace TableTennisLive.Core.Models;

public sealed record DrawEvent(int Id, string Name, DateTimeOffset Start, DateTimeOffset End)
{
    public string DisplayName => Name;
}
public sealed record DrawPlayer(string Name, string Raw, string CountryCode, string Score,
    bool Winner, string PreviousMatch, string PlayerId)
{
    public string Registration { get; init; } = "";
    public string Flag => Services.CountryFlags.FromCode(CountryCode);
    public string NameWithFlag => Flag.Length == 0 ? Name : $"{Flag}  {Name}";
}
public sealed record DrawMatch(string Id, int Order, DrawPlayer Left, DrawPlayer Right,
    string Date, string Time, IReadOnlyList<SetScore> Sets, bool Bye);
public sealed record DrawRound(string Code, string Title, IReadOnlyList<DrawMatch> Matches);
public sealed record DrawStage(string Code, IReadOnlyList<DrawRound> Rounds)
{
    public string DisplayName => Code switch
    {
        "MAIN" or "MAINDRAW" => "正赛", "QUAL" or "QUALIFICATION" => "资格赛", _ => Code
    };
}
