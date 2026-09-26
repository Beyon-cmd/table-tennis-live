namespace TableTennisLive.Core.Models;

public sealed record TrendPoint(int SetNumber, int ScoreA, int ScoreB,
    bool Final, IReadOnlyList<string> Events)
{
    public int Progress => ScoreA + ScoreB;
    public int Difference => ScoreA - ScoreB;
}
