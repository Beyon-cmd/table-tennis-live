using TableTennisLive.Core.Services;

namespace TableTennisLive.Core.Models;

public sealed record RankingEntry(string EventCode, int Rank, string PlayerName,
    string CountryCode, int Points, int Change, string PlayerId, DateTimeOffset? Published)
{
    public string PortraitUri { get; init; } = "";
    public string CategoryCode { get; init; } = "SEN";
    public string AgeCategoryCode { get; init; } = "";
    public string PartnerName { get; init; } = "";
    public string PartnerId { get; init; } = "";
    public string PartnerCountryCode { get; init; } = "";
    public string PairId { get; init; } = "";
    public bool IsPair => PartnerName.Length > 0;
    public string DisplayName => IsPair
        ? $"{ChineseNames.Display(PlayerName)} / {ChineseNames.Display(PartnerName)}"
        : ChineseNames.Display(PlayerName);
    public string CountryFlagUri => CountryFlags.AssetUri(CountryCode.ToUpperInvariant());
    public string PartnerCountryFlagUri => IsPair && PartnerCountryCode != CountryCode
        ? CountryFlags.AssetUri(PartnerCountryCode.ToUpperInvariant()) : "";
    public int PartnerFlagWidth => PartnerCountryFlagUri.Length > 0 ? 23 : 0;
    public string CountryDisplay => IsPair && PartnerCountryCode != CountryCode
        ? $"{CountryCode}/{PartnerCountryCode}" : CountryCode;
    public string AgeDisplay => CategoryCode == "YOU" ? AgeCategoryCode : "";
    public string AvatarGlyph => IsPair ? "\uE716" : "\uE77B";
    public int AvatarWidth => IsPair ? 0 : 38;
    public double PlaceholderOpacity => IsPair || PortraitUri.Length > 0 ? 0 : 0.48;
    public string ChangeDisplay => Change > 0 ? $"↑ {Change}" :
        Change < 0 ? $"↓ {Math.Abs((long)Change)}" : "—";
}
