using System.Text;
using System.Text.RegularExpressions;

namespace TableTennisLive.Core.Services;

public static class CountryFlags
{
    private static readonly Regex Suffix = new(@"\(([A-Z]{3})\)\s*$",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);
    private static readonly Dictionary<string, string> Codes = new(StringComparer.OrdinalIgnoreCase)
    {
        ["CHN"] = "CN", ["JPN"] = "JP", ["KOR"] = "KR", ["TPE"] = "TW",
        ["HKG"] = "HK", ["MAC"] = "MO", ["GER"] = "DE", ["FRA"] = "FR",
        ["SWE"] = "SE", ["USA"] = "US", ["CAN"] = "CA", ["BRA"] = "BR",
        ["IND"] = "IN", ["SGP"] = "SG", ["AUS"] = "AU", ["NZL"] = "NZ",
        ["ESP"] = "ES", ["ITA"] = "IT", ["POR"] = "PT", ["AUT"] = "AT",
        ["SUI"] = "CH", ["CZE"] = "CZ", ["SVK"] = "SK", ["POL"] = "PL",
        ["ROU"] = "RO", ["HUN"] = "HU", ["DEN"] = "DK", ["NOR"] = "NO",
        ["FIN"] = "FI", ["BEL"] = "BE", ["NED"] = "NL", ["UKR"] = "UA",
        ["KAZ"] = "KZ", ["UZB"] = "UZ", ["INA"] = "ID", ["THA"] = "TH",
        ["MAS"] = "MY", ["VIE"] = "VN", ["PHI"] = "PH", ["EGY"] = "EG",
        ["NGR"] = "NG", ["RSA"] = "ZA", ["MEX"] = "MX", ["PUR"] = "PR",
        ["ARG"] = "AR", ["CRO"] = "HR", ["SLO"] = "SI", ["SRB"] = "RS",
        ["TUR"] = "TR", ["GRE"] = "GR", ["GBR"] = "GB", ["ENG"] = "GB",
        ["WAL"] = "GB", ["SCO"] = "GB", ["IRL"] = "IE", ["ISR"] = "IL",
        ["IRI"] = "IR", ["KSA"] = "SA", ["QAT"] = "QA", ["UAE"] = "AE",
        ["NEP"] = "NP", ["PRK"] = "KP", ["MGL"] = "MN", ["LUX"] = "LU",
        ["LAT"] = "LV", ["LTU"] = "LT", ["EST"] = "EE", ["BUL"] = "BG"
    };

    public static string FromName(string name)
    {
        var match = Suffix.Match(name);
        return match.Success ? FromCode(match.Groups[1].Value) : "";
    }

    public static string CodeFromName(string name)
    {
        var match = Suffix.Match(name);
        return match.Success ? match.Groups[1].Value.ToUpperInvariant() : "";
    }

    public static string WithoutCode(string displayName) => Suffix.Replace(displayName, "").TrimEnd();

    public static string AssetUri(string code) =>
        code.Length == 3 && code.All(c => c is >= 'A' and <= 'Z')
            ? $"ms-appx:///Assets/Flags/{code}.png" : "";

    public static string FromCode(string code)
    {
        if (code.Length == 2) code = code.ToUpperInvariant();
        else if (!Codes.TryGetValue(code, out code!)) return "";
        if (code.Length != 2 || !code.All(c => c is >= 'A' and <= 'Z')) return "";
        return string.Concat(code.Select(c => char.ConvertFromUtf32(0x1F1E6 + c - 'A')));
    }
}
