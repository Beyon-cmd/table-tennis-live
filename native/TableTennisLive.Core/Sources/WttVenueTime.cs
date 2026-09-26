using System.Text.Json;
using TableTennisLive.Core.Services;

namespace TableTennisLive.Core.Sources;

/// <summary>WTT event timeZoneId to the fixed offset published by its website.</summary>
public static class WttVenueTime
{
    private static readonly IReadOnlyDictionary<int, TimeSpan> Offsets = Build();

    private static IReadOnlyDictionary<int, TimeSpan> Build()
    {
        var groups = new (int Minutes, string Ids)[]
        {
            (-720,"3"),(-660,"4"),(-600,"5"),(-540,"6"),(-480,"7 9"),
            (-420,"8 10 11 12"),(-360,"13 14 15 16"),(-300,"17 18 19"),
            (-270,"20"),(-240,"21 22 23 24 25"),(-210,"26"),
            (-180,"27 28 29 30 31 32"),(-120,"33 34"),(-60,"35 36"),
            (0,"37 38 39 41 42"),(60,"40 43 44 45 46 47 48"),
            (120,"49 50 51 52 53 54 55 57 58 61"),
            (180,"56 59 60 62 63 64"),(210,"66"),
            (240,"65 67 68 69 70 71"),(270,"72"),
            (300,"73 74 75"),(330,"76 77"),(345,"78"),
            (360,"79 80"),(390,"81"),(420,"82 83"),
            (480,"84 85 86 87 88 89 90"),(540,"91 92 99"),
            (570,"93 94"),(600,"95 96 97 98"),(660,"100 101"),
            (720,"102 103 104 105 106"),(780,"107 108")
        };
        return groups.SelectMany(group => group.Ids.Split(' ').Select(id =>
            new KeyValuePair<int, TimeSpan>(int.Parse(id), TimeSpan.FromMinutes(group.Minutes))))
            .ToDictionary(pair => pair.Key, pair => pair.Value);
    }

    public static TimeSpan? Offset(JsonElement eventRow) =>
        Offsets.TryGetValue(eventRow.At("timeZoneId").Number(), out var offset) ? offset : null;

    public static DateTimeOffset? ToLocal(string venueTime, TimeSpan? offset)
    {
        if (offset is null || !DateTime.TryParse(venueTime, out var wall)) return null;
        return new DateTimeOffset(DateTime.SpecifyKind(wall, DateTimeKind.Unspecified), offset.Value)
            .ToLocalTime();
    }
}
