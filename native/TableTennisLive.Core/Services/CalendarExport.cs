using System.Security.Cryptography;
using System.Text;
using TableTennisLive.Core.Models;

namespace TableTennisLive.Core.Services;

public static class CalendarExport
{
    public static byte[] Build(Match match, DateTimeOffset? now = null)
    {
        if (match.Status != MatchStatus.Upcoming)
            throw new ArgumentException("只能导出尚未开始的比赛");
        var start = match.StartTime.ToUniversalTime();
        var end = start.AddHours(match.Competition.Contains("团体") ? 3 : 2);
        var stamp = (now ?? DateTimeOffset.UtcNow).ToUniversalTime();
        var uid = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(match.Id)))
            [..24].ToLowerInvariant() + "@tabletennislive.local";
        var local = start.ToLocalTime();
        var beijing = start.ToOffset(TimeSpan.FromHours(8));
        var description = $"本机时间 {local:yyyy-MM-dd HH:mm}  ·  北京时间 {beijing:yyyy-MM-dd HH:mm}\n" +
            "开始时间来自当前赛程；结束时间仅为日历占位，实际赛程可能调整。";
        var fields = new[]
        {
            "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Table Tennis Live//Match Calendar//ZH",
            "CALSCALE:GREGORIAN", "BEGIN:VEVENT", "UID:" + uid,
            $"DTSTAMP:{stamp:yyyyMMddTHHmmssZ}", $"DTSTART:{start:yyyyMMddTHHmmssZ}",
            $"DTEND:{end:yyyyMMddTHHmmssZ}",
            "SUMMARY:" + Escape($"{match.PlayerA} vs {match.PlayerB} · {match.Competition}"),
            "DESCRIPTION:" + Escape(description), "END:VEVENT", "END:VCALENDAR"
        };
        return Encoding.UTF8.GetBytes(string.Join("\r\n", fields.SelectMany(Fold)) + "\r\n");
    }

    private static string Escape(string value) => value.Replace("\\", "\\\\")
        .Replace("\r\n", "\n").Replace('\r', '\n').Replace("\n", "\\n")
        .Replace(";", "\\;").Replace(",", "\\,");

    private static IEnumerable<string> Fold(string value)
    {
        var line = new StringBuilder();
        foreach (var rune in value.EnumerateRunes())
        {
            var text = rune.ToString();
            if (Encoding.UTF8.GetByteCount(line.ToString() + text) > 75)
            {
                yield return line.ToString();
                line.Clear();
                line.Append(' ');
            }
            line.Append(text);
        }
        yield return line.ToString();
    }
}
