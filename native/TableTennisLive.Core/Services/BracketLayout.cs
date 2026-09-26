using TableTennisLive.Core.Models;

namespace TableTennisLive.Core.Services;

public sealed record BracketNode(DrawMatch Match, double X, double Y);
public sealed record BracketEdge(BracketNode From, BracketNode To);
public sealed record BracketGeometry(IReadOnlyList<BracketNode> Nodes,
    IReadOnlyList<BracketEdge> Edges, double Width, double Height);

/// <summary>Places rounds by predecessor IDs validated or derived from official draw order.</summary>
public static class BracketLayout
{
    public const double CardWidth = 300;
    public const double CardHeight = 116;
    public const double ColumnGap = 68;
    public const double RowStep = 148;

    public static BracketGeometry Build(IReadOnlyList<DrawRound> rounds)
    {
        var nodes = new List<BracketNode>();
        var edges = new List<BracketEdge>();
        var byId = new Dictionary<string, BracketNode>(StringComparer.Ordinal);
        double height = 180;
        for (var column = 0; column < rounds.Count; column++)
        {
            double floor = 60;
            var x = 20 + column * (CardWidth + ColumnGap);
            var row = 0;
            foreach (var match in rounds[column].Matches)
            {
                var parents = new[] { match.Left.PreviousMatch, match.Right.PreviousMatch }
                    .Where(id => id.Length > 0 && byId.ContainsKey(id))
                    .Distinct(StringComparer.Ordinal).Select(id => byId[id]).ToArray();
                var target = parents.Length > 0 ? parents.Average(parent => parent.Y) :
                    60 + row * RowStep;
                var y = Math.Max(floor, target);
                floor = y + RowStep;
                var node = new BracketNode(match, x, y);
                nodes.Add(node);
                foreach (var parent in parents) edges.Add(new(parent, node));
                if (match.Id.Length > 0) byId[match.Id] = node;
                height = Math.Max(height, y + CardHeight + 28);
                row++;
            }
        }
        var width = rounds.Count == 0 ? 800 :
            20 + rounds.Count * CardWidth + (rounds.Count - 1) * ColumnGap + 28;
        return new(nodes, edges, width, height);
    }
}
