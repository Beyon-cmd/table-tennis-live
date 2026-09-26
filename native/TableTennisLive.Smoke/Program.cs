using System.Text.Json;
using TableTennisLive.Core.Models;
using TableTennisLive.Core.Services;
using TableTennisLive.Core.Sources;

static void Require(bool condition, string message)
{
    if (!condition) throw new Exception(message);
}

using (var document = JsonDocument.Parse("{\"timeZoneId\":73}"))
{
    var local = WttVenueTime.ToLocal("2026-09-20T17:00:00",
        WttVenueTime.Offset(document.RootElement));
    Require(local?.ToUniversalTime() == new DateTimeOffset(2026, 9, 20, 12, 0, 0,
        TimeSpan.Zero), "Astana venue/UTC conversion");
}

using (var document = JsonDocument.Parse("""
    {"Key":"fixture","DateTimeRaw":"2026-09-25T12:00:00+09:00",
     "Home":{"Name":"A","Org":"CHN","Result":"2","Splits":[{"Res":"11"},{"Res":"10"},{"Res":"11"},{"Res":"5"}]},
     "Away":{"Name":"B","Org":"JPN","Result":"1","Splits":[{"Res":"7"},{"Res":"12"},{"Res":"7"},{"Res":"11"}]},
     "Status":"LIVE","EventDesc":"Mixed Doubles"}
    """))
{
    var match = AsianGamesSource.ParseSchedule(document.RootElement)!;
    Require(match.ScoreA == 2 && match.ScoreB == 2 && match.ScoreReconciled,
        "completed sets must correct delayed aggregate");
    Require(match.Sets.Count == 4 && match.CurrentSet is null, "set completion");
    Require(match.PlayerACountryCode == "CHN" && match.PlayerBCountryCode == "JPN",
        "Asian Games competitors retain flag identity");
}

var before = new Match("id", "test", "competition", MatchStatus.Live,
    DateTimeOffset.UtcNow, "A", "B") { ScoreA = 1, ScoreB = 0, LastUpdate = DateTimeOffset.UtcNow };
var after = before with { LastUpdate = DateTimeOffset.UtcNow.AddSeconds(1) };
Require(before.ContentFingerprint() == after.ContentFingerprint(),
    "poll timestamp must not redraw a score card");
var playerRows = new[] { new RankingEntry("WS", 1, "WANG Manyu", "CHN", 9115,
    0, "121411", null) };
Require(playerRows[0].CountryFlagUri.EndsWith("/CHN.png") &&
    playerRows[0].ChangeDisplay == "—" &&
    (playerRows[0] with { Change = 3 }).ChangeDisplay == "↑ 3" &&
    (playerRows[0] with { Change = -2 }).ChangeDisplay == "↓ 2",
    "ranking association and movement remain visible");
Require(PlayerProfileService.ResolveId("王曼昱", "WANG Manyu", "CHN", "", playerRows) == "121411",
    "unique official player identity");
Require(PlayerProfileService.ResolveId("王曼昱", "", "", "", playerRows) == "121411",
    "uniquely mapped Chinese display name resolves against official ranking");
var knownChinese = new[] { new RankingEntry("MS", 1, "WANG Chuqin", "CHN", 8157,
    0, "121558", null) };
Require(PlayerProfileService.ResolveId("王楚钦", "王楚钦", "CHN", "", knownChinese) == "121558",
    "Chinese display name uniquely resolves to official ranking identity");
var knownPair = new RankingEntry("MD", 1, "Alexis LEBRUN", "FRA", 4658, 0,
    "132992", null) { PartnerName = "Felix LEBRUN", PartnerId = "135977",
        PartnerCountryCode = "FRA" };
Require(PlayerProfileService.ResolveId("Felix LEBRUN", "Felix LEBRUN", "FRA", "",
    [knownPair]) == "135977", "doubles partner identity is independently resolvable");
using (var document = JsonDocument.Parse("""
    {"Result":[{"SubEventCode":"MS","CurrentRank":1,"RankingPointsYTD":8157,
      "PlayerName":"WANG Chuqin","CountryCode":"CHN","RankingDifference":0,
      "IttfId":"121411","AgeCategoryCode":"U19","PublishDate":"2026-09-21"}]}
    """))
{
    var youth = RankingService.ParseSingles(document.RootElement, "YOU").Single();
    Require(youth.CategoryCode == "YOU" && youth.EventCode == "MS" &&
        youth.AgeDisplay == "U19", "youth singles ranking keeps age category");
}
using (var document = JsonDocument.Parse("""
    {"Result":[{"SubEventCode":"XD","CurrentRank":1,"Points":3200,
      "PlayerName1":"WANG Chuqin","CountryCode1":"CHN","IttfId1":"121411",
      "PlayerName1d":"SUN Yingsha","CountryCode1d":"CHN","IttfId1d":"131411",
      "PairId":"p1","RankingDifference":2,"AgeCategoryCode":"U19",
      "PublishDate":"2026-09-21"}]}
    """))
{
    var pair = RankingService.ParsePairs(document.RootElement, "YOU").Single();
    Require(pair.IsPair && pair.CategoryCode == "YOU" && pair.EventCode == "XD" &&
        pair.PartnerId == "131411" && pair.DisplayName.Contains('/'),
        "youth doubles ranking keeps both player identities");
}
using (var document = JsonDocument.Parse("""
    {"additional_data":{"PlayerData":[{"IttfId":"121411","PlayerName":"WANG Manyu",
      "Gender":"F","CountryCode":"CHN"}],"StatsData":[
      {"IttfId":"121411","SubeventCode":"WS","current_year_total_wins":22,
       "current_year_total_matches":28}]}}
    """))
{
    var profile = PlayerProfileService.Parse(document.RootElement, "121411", playerRows[0]);
    Require(profile?.YearWins == 22 && profile.YearMatches == 28 && profile.WinRate == 79,
        "player profile retains the numerator and denominator for precise win rate");
}
using (var document = JsonDocument.Parse("""
    {"ranking":5,"rankingPoints":4000,"additional_data":{"PlayerData":[
      {"IttfId":"121411","PlayerName":"WANG Manyu","Gender":"F","CountryCode":"CHN"}]}}
    """))
{
    var profile = PlayerProfileService.Parse(document.RootElement, "121411", playerRows[0]);
    Require(profile?.Rank == 1 && profile.Points == 9115,
        "current official senior singles row overrides ambiguous player-detail rank");
}
var settingsFixture = Path.Combine(Path.GetTempPath(),
    "ttl-compat-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(settingsFixture);
try
{
    File.WriteAllText(Path.Combine(settingsFixture, "favorites.json"),
        """["WTT-42","Asian-7"]""");
    File.WriteAllText(Path.Combine(settingsFixture, "settings.json"),
        """{"alerts":{"start":true,"score":false,"final":true},"theme":"light"}""");
    var favorites = new FavoriteStore(settingsFixture);
    Require(favorites.Contains("WTT-42") && favorites.Contains("Asian-7"),
        "native favorites must read the Python JSON format");
    favorites.Toggle("WTT-42");
    Require(!new FavoriteStore(settingsFixture).Contains("WTT-42") &&
        new FavoriteStore(settingsFixture).Contains("Asian-7"),
        "favorite edits persist without losing other IDs");
    var fixtureAlerts = new AlertSettings(settingsFixture);
    Require(fixtureAlerts.Enabled("start") && fixtureAlerts.Enabled("final") &&
        !fixtureAlerts.Enabled("score"), "native alerts must read the Python JSON format");
    fixtureAlerts.Set("score", true);
    using var settingsDocument = JsonDocument.Parse(File.ReadAllText(
        Path.Combine(settingsFixture, "settings.json")));
    Require(new AlertSettings(settingsFixture).Enabled("score") &&
        settingsDocument.RootElement.GetProperty("theme").GetString() == "light",
        "alert edits persist without dropping another setting");
    var config = CloudConfig.Create("https://demo.supabase.co/rest/v1/", "sb_publishable_test");
    Require(config.ProjectUrl.ToString() == "https://demo.supabase.co/",
        "a REST endpoint must normalize to its Supabase project origin");
    config.Save(settingsFixture);
    Require(CloudConfig.Load(settingsFixture)?.ProjectUrl == config.ProjectUrl,
        "cloud configuration must round trip outside the application binary");
    var userId = Guid.NewGuid().ToString();
    favorites.ActivateAccount(userId);
    Require(favorites.Contains("Asian-7") && favorites.Pending["Asian-7"],
        "first sign-in queues anonymous favorites without discarding them");
    favorites.Acknowledge(new Dictionary<string, bool> { ["Asian-7"] = true });
    favorites.ApplyRemote(["Remote-9"]);
    Require(favorites.Contains("Remote-9") && !favorites.Contains("Asian-7"),
        "cloud snapshot applies after acknowledged local operations");
    favorites.Toggle("Remote-9");
    favorites.ApplyRemote(["Remote-9"]);
    Require(!favorites.Contains("Remote-9") &&
        favorites.Pending.TryGetValue("Remote-9", out var queuedRemoval) && !queuedRemoval,
        "offline removals must survive a stale remote snapshot");
    favorites.ActivateAccount(null);
    Require(favorites.Contains("Asian-7") && !favorites.Contains("Remote-9"),
        "sign-out restores separate anonymous favorites");
    if (OperatingSystem.IsWindows())
    {
        var session = new CloudSession(userId, "a@example.com", "access", "refresh-test",
            DateTimeOffset.UtcNow.AddHours(1));
        var sessionStore = new CloudSessionStore(settingsFixture);
        sessionStore.Save(session);
        Require(sessionStore.LoadRefreshToken() == "refresh-test" &&
            !File.ReadAllText(Path.Combine(settingsFixture, "cloud_session.json"))
                .Contains("refresh-test"),
            "refresh tokens round trip via Windows DPAPI without plaintext storage");
    }
    try
    {
        CloudConfig.Create("https://demo.supabase.co", "sb_secret_test");
        throw new Exception("secret key was accepted");
    }
    catch (ArgumentException) { }
}
finally { Directory.Delete(settingsFixture, recursive: true); }
var archive = HistoricalMajorArchive.Load();
Require(archive.Count == 101 && archive.All(m => m.Status == MatchStatus.Finished),
    "verified historical finals must stay archived, never LIVE");
Require(archive.Any(m => m.Games.Count > 0 && m.Games.Any(g => g.Sets.Count > 0)),
    "verified team submatches and per-game points");
Require(archive.Count(m => m.MajorCategory == "奥运会") > 0 &&
    archive.Count(m => m.MajorCategory.Contains("世锦赛")) > 0 &&
    archive.Count(m => m.MajorCategory.Contains("世界杯")) > 0,
    "all three major archives retain readable categories");
Require(new[] { "奥运会", "世锦赛", "世界杯" }.All(category =>
    archive.Any(m => m.MajorCategory.Contains(category) && m.ScoreKnown &&
        m.Sets.Count > 0)), "historical majors retain final scores and per-game points");
var wttReconciled = WttSource.ReconcileScore(2, 1,
    [new(11, 7), new(10, 12), new(11, 7), new(5, 11)]);
Require(wttReconciled == (2, 2, true), "completed set wins correct a lagging aggregate");
using (var document = JsonDocument.Parse("""
    {"resultStatus":"OFFICIAL","matchCardResult":{
      "OverallScores":"2-1","GameScores":"11-7,10-12,11-7,5-11"}}
    """))
{
    var summary = before with { ScoreA = 2, ScoreB = 1, ScoreKnown = true,
        Sets = [new(11, 7), new(10, 12)] };
    var detail = WttSource.MergeDetail(summary, document.RootElement);
    Require(detail.Status == MatchStatus.Finished && detail.ScoreA == 2 &&
        detail.ScoreB == 2 && detail.Sets.Count == 4 && detail.ScoreReconciled,
        "on-demand WTT detail must restore official games and correct lagging total");
    var nextPoll = WttSource.PreferRichDetail(summary, detail);
    Require(nextPoll.ScoreB == 2 && nextPoll.Sets.Count == 4 &&
        nextPoll.Status == MatchStatus.Finished,
        "a summary poll cannot overwrite a richer WTT detail");
    var progressed = summary with { ScoreA = 3, ScoreB = 2 };
    Require(ReferenceEquals(WttSource.PreferRichDetail(progressed, detail), progressed),
        "a newer aggregate score supersedes the detail cache");
    using var oldDocument = JsonDocument.Parse("""
        {"matchCardResult":{"OverallScores":"1-0","GameScores":"11-7"}}
        """);
    Require(WttSource.MergeDetail(detail, oldDocument.RootElement) == detail,
        "an older WTT match card cannot regress the visible score");
}
Require(ChineseNames.Display("WANG Manyu (CHN)") == "王曼昱 (CHN)",
    "verified player translation preserves the association");
Require(ChineseNames.Display("UNKNOWN Player") == "UNKNOWN Player",
    "unknown names must not be guessed");
Require(CountryFlags.FromName("WANG Manyu (CHN)") == "🇨🇳" &&
    CountryFlags.FromCode("GER") == "🇩🇪" && CountryFlags.FromCode("???") == "",
    "flags use verified country codes only");
var nobody = new DrawPlayer("待定", "", "", "—", false, "", "");
var firstRound = new DrawMatch("round-1", 1, nobody, nobody, "", "", [], false);
var advancing = new DrawMatch("round-2", 1,
    nobody with { PreviousMatch = "round-1" }, nobody, "", "", [], false);
var bracket = BracketLayout.Build([
    new DrawRound("R1", "第一轮", [firstRound]),
    new DrawRound("R2", "第二轮", [advancing])
]);
Require(bracket.Nodes.Count == 2 && bracket.Edges.Count == 1 &&
    bracket.Edges[0].From.Match.Id == "round-1" &&
    bracket.Nodes[1].X > bracket.Nodes[0].X,
    "bracket links only supplied previous-match identifiers");
var unverifiedLink = BracketLayout.Build([
    new DrawRound("R1", "第一轮", [firstRound]),
    new DrawRound("R2", "第二轮", [advancing with
    { Left = advancing.Left with { PreviousMatch = "missing-id" } }])
]);
Require(unverifiedLink.Edges.Count == 0,
    "bracket never draws a guessed connection");
using (var document = JsonDocument.Parse("""
    [{"Code":"MAINDRAW","Phases":[
      {"Code":"M.SINGLES.R64-","Matches":[
        {"Home":{"Reg":"1","Name":"A","Win":true},
         "Away":{"Reg":"2","Name":"B"},"Info":{"Key":"first"}},
        {"Home":{"Reg":"3","Name":"C","Win":true},
         "Away":{"Reg":"4","Name":"D"},"Info":{"Key":"second"}}]},
      {"Code":"M.SINGLES.R32-","Matches":[
        {"Home":{"Reg":"1","Name":"A"},
         "Away":{"Reg":"4","Name":"D"},"Info":{"Key":"next"}}]}
    ]}]
    """))
{
    var rounds = AsianGamesDrawService.Parse(document.RootElement,
        "M.SINGLES-----------")[0].Rounds;
    Require(rounds[1].Matches[0].Left.PreviousMatch == "first" &&
        rounds[1].Matches[0].Right.PreviousMatch == "",
        "Asian Games draw links bracket slots but rejects a contradictory winner");
    var layout = BracketLayout.Build(rounds);
    Require(layout.Edges.Count == 1 && layout.Nodes.Count == 3 &&
        layout.Nodes[1].Y - layout.Nodes[0].Y >= BracketLayout.CardHeight,
        "connected bracket cards retain separate layout positions");
}
var trend = new ScoreTrendStore();
trend.Observe(before with { Sets = [new(11, 9)], CurrentSet = new(3, 2) });
Require(trend.Points("id").Count == 2 && trend.Points("id")[1].Difference == 1,
    "trend contains only observed completed and current set scores");
var calendar = System.Text.Encoding.UTF8.GetString(CalendarExport.Build(before with
{
    Status = MatchStatus.Upcoming,
    StartTime = new DateTimeOffset(2026, 9, 25, 16, 0, 0, TimeSpan.FromHours(8))
}, new DateTimeOffset(2026, 9, 25, 0, 0, 0, TimeSpan.Zero)));
var unfoldedCalendar = calendar.Replace("\r\n ", "");
Require(unfoldedCalendar.Contains("DTSTART:20260925T080000Z") &&
    unfoldedCalendar.Contains("北京时间 2026-09-25 16:00"),
    "ICS uses real UTC start and displays China time");
var alerts = new MatchAlertTracker();
var upcoming = before with { Status = MatchStatus.Upcoming };
Require(alerts.Update(upcoming, true, _ => true).Count == 0,
    "initial favorite snapshot never sends a false alert");
Require(alerts.Update(before, true, _ => true).Single().Kind == "start",
    "upcoming to live sends one start alert");
Require(alerts.Update(before, true, _ => true).Count == 0,
    "repeated polls do not duplicate an alert");
Console.WriteLine("parser invariants OK");

if (args.Contains("--live"))
{
    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(45));
    using var ranking = new RankingService();
    try
    {
        var rows = await ranking.RefreshAsync(cts.Token);
        Console.WriteLine($"rankings: MS {rows.Count(x => x.EventCode == "MS")}, " +
            $"WS {rows.Count(x => x.EventCode == "WS")}, " +
            $"published {rows.FirstOrDefault()?.Published:yyyy-MM-dd}");
        var known = rows.FirstOrDefault(x => x.PlayerId.Length > 0);
        if (known is not null)
        {
            using var profiles = new PlayerProfileService();
            var profile = await profiles.GetAsync(known.PlayerId, known, cts.Token);
            Console.WriteLine($"profile: {profile?.Name ?? "no verified result"}, " +
                $"photo {(profile?.Portrait is null ? "no" : "yes")}");
        }
    }
    catch (Exception error) { Console.WriteLine($"rankings: ERROR {error}"); }
    IMatchSource[] sources = [new AsianGamesSource(), new WttSource(),
        new TtblSource(), new TLeagueSource()];
    var tasks = sources.Select(async source =>
    {
        try
        {
            var matches = await source.GetMatchesAsync(cts.Token);
            Console.WriteLine($"{source.Name}: {matches.Count} matches, " +
                $"{matches.Count(m => m.Status == MatchStatus.Live)} LIVE");
            foreach (var row in matches.Where(m => m.Status == MatchStatus.Live).Take(3))
                Console.WriteLine($"  {row.PlayerA} {row.ScoreA}:{row.ScoreB} {row.PlayerB}");
        }
        catch (Exception error)
        {
            Console.WriteLine($"{source.Name}: ERROR {error}");
        }
        finally { (source as IDisposable)?.Dispose(); }
    });
    await Task.WhenAll(tasks);
}

if (args.Contains("--draws"))
{
    using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(40));
    using var draws = new WttDrawService();
    var events = await draws.GetEventsAsync(cts.Token);
    Console.WriteLine($"WTT draw events: {events.Count}");
    foreach (var eventWithDraw in events.Take(6))
    {
        var stages = await draws.GetDrawAsync(eventWithDraw.Id, "男单", cts.Token);
        Console.WriteLine($"{eventWithDraw.Name}: {stages.Count} stages, " +
            $"{stages.Sum(s => s.Rounds.Sum(r => r.Matches.Count))} matches");
        if (stages.Count > 0) break;
    }
    using var asianDraws = new AsianGamesDrawService();
    var asianStages = await asianDraws.GetDrawAsync("男单", cts.Token);
    Console.WriteLine($"Asian Games men's singles: {asianStages.Count} stages, " +
        $"{asianStages.Sum(s => s.Rounds.Sum(r => r.Matches.Count))} matches");
    foreach (var stage in asianStages)
    {
        Console.WriteLine("  " + string.Join(", ", stage.Rounds.Select(round =>
            $"{round.Title}={round.Matches.Count}")));
        Console.WriteLine($"  {BracketLayout.Build(stage.Rounds).Edges.Count} verified or " +
            "structurally mapped bracket links");
    }
    if (args.Contains("--inspect-asian-draw"))
    {
        using var asianSource = new AsianGamesSource();
        var raw = await asianSource.GetBracketPayloadAsync("M.SINGLES-----------", cts.Token);
        foreach (var phase in raw.Items().SelectMany(bracket => bracket.At("Phases").Items()))
        {
            var example = phase.At("Matches").Items().FirstOrDefault();
            Console.WriteLine($"  raw {phase.At("Code").Text()}: " +
                $"rows={phase.At("Matches").Items().Count()}, first={example}");
        }
    }
}
