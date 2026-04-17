using UnityEngine;
using UnityEditor;
using System.Collections.Generic;
using System.IO;

#region Export Models

[System.Serializable]
public class ExportEvent
{
    public string eventID;
    public string eventName;
    public int maxTriggers;
    public List<string> requiresSequences;
    public List<string> startsSequences;
    public List<string> endsSequences;
    public List<ExportCondition> conditions;
    public List<ExportMutation> mutates;
}

[System.Serializable]
public class ExportCondition
{
    public string variable;
    public string @operator;
    public string value;
    public string type;
}

[System.Serializable]
public class ExportMutation
{
    public string variable;

    // Only one of these should be populated
    public int delta;
    public string value;
}

[System.Serializable]
public class Wrapper
{
    public List<ExportEvent> events;
}

#endregion

public static class EventExporter
{
    [MenuItem("Tools/Export System Events To JSON")]
    public static void Export()
    {
        string[] guids = AssetDatabase.FindAssets("t:SystemEvent");

        List<SystemEvent> assets = new List<SystemEvent>();
        Dictionary<SystemEvent, string> assetPaths = new Dictionary<SystemEvent, string>();

        List<ExportEvent> exportEvents = new List<ExportEvent>();

        foreach (string guid in guids)
        {
            string path = AssetDatabase.GUIDToAssetPath(guid);
            SystemEvent asset = AssetDatabase.LoadAssetAtPath<SystemEvent>(path);

            if (asset == null)
            {
                Debug.LogError("Failed to load SystemEvent at path: " + path);
                continue;
            }

            assets.Add(asset);
            assetPaths[asset] = path;
        }

        if (!ValidateAssets(assets, assetPaths))
        {
            Debug.LogError("Export aborted due to validation errors. See logs above for details.");
            return;
        }

        foreach (SystemEvent asset in assets)
        {
            ExportEvent exportEvent = new ExportEvent();
            exportEvent.eventID = NormalizeToken(asset.eventID);
            exportEvent.eventName = asset.eventName;
            exportEvent.maxTriggers = asset.maxTriggers;

            // SEQUENCES
            exportEvent.requiresSequences = NormalizeList(asset.requiresSequences);
            exportEvent.startsSequences = NormalizeList(asset.startsSequences);
            exportEvent.endsSequences = NormalizeList(asset.endsSequences);

            // Conditions
            exportEvent.conditions = new List<ExportCondition>();
            foreach (var condition in asset.conditions)
            {
                exportEvent.conditions.Add(new ExportCondition
                {
                    variable = $"{condition.scope.Trim().ToLower()}.{condition.name.Trim().ToLower()}",
                    @operator = ToSymbol(condition.comparisonOperator),
                    value = condition.valueType == ValueType.Int
                        ? condition.intValue.ToString()
                        : condition.stateValue.ToLower(),
                    type = condition.valueType.ToString().ToLower()
                });
            }

            // MUTATIONS
            exportEvent.mutates = new List<ExportMutation>();
            foreach (var mutation in asset.mutates)
            {
                ExportMutation exportMutation = new ExportMutation();
                exportMutation.variable = mutation.scope.ToString().ToLower() + "." + mutation.name.ToLower();

                if (mutation.mutationType == MutationType.Delta)
                {
                    exportMutation.delta = mutation.delta;
                    exportMutation.value = null; // ensure value is null when using delta
                }
                else
                {
                    exportMutation.delta = 0;
                    exportMutation.value = mutation.state.ToLower(); // assuming state is a string, convert to lowercase for consistency
                }

                exportEvent.mutates.Add(exportMutation);
            }

            exportEvents.Add(exportEvent);
        }

        Wrapper wrapper = new Wrapper { events = exportEvents };

        string json = JsonUtility.ToJson(wrapper, true);

        string outputPath = Path.Combine(Application.dataPath, "system_events.json");
        File.WriteAllText(outputPath, json);

        Debug.Log("System Events exported to: " + outputPath);
    }

    private static string ToSymbol(ComparisonOperator op)
    {
        switch (op)
        {
            case ComparisonOperator.LessThan: return "<";
            case ComparisonOperator.LessThanOrEqual: return "<=";
            case ComparisonOperator.GreaterThan: return ">";
            case ComparisonOperator.GreaterThanOrEqual: return ">=";
            case ComparisonOperator.Equal: return "=";
            default: return "?";
        }
    }

    private static bool ValidateAssets(List<SystemEvent> assets, Dictionary<SystemEvent, string> assetPaths)
    {
        bool hasErrors = false;

        Dictionary<string, SystemEvent> eventIdLookup = new Dictionary<string, SystemEvent>();
        HashSet<string> knownSequences = new HashSet<string>();

        foreach (SystemEvent asset in assets)
        {
            string normalizedId = NormalizeToken(asset.eventID);
            if (string.IsNullOrEmpty(normalizedId))
            {
                LogValidationError(asset, assetPaths, "EventID is empty or whitespace.");
                hasErrors = true;
            }
            else
            {
                string trimmedId = asset.eventID == null ? string.Empty : asset.eventID.Trim();
                if (normalizedId != trimmedId)
                {
                    LogValidationWarning(asset, assetPaths, $"EventID will be normalized from '{trimmedId}' to '{normalizedId}'.");
                }
            }

            if (eventIdLookup.ContainsKey(normalizedId))
            {
                SystemEvent existing = eventIdLookup[normalizedId];
                LogValidationError(asset, assetPaths, $"Duplicate eventID '{asset.eventID}'. Also defined in: {GetPath(existing, assetPaths)}");
                hasErrors = true;
            }
            else
            {
                eventIdLookup[normalizedId] = asset;
            }

            CollectSequences(asset, assetPaths, knownSequences, ref hasErrors);
        }

        foreach (SystemEvent asset in assets)
        {
            ValidateRequiredSequences(asset, assetPaths, knownSequences, ref hasErrors);
            ValidateConditions(asset, assetPaths);
            ValidateMutations(asset, assetPaths, ref hasErrors);
        }

        return !hasErrors;
    }

    private static void CollectSequences(SystemEvent asset, Dictionary<SystemEvent, string> assetPaths, HashSet<string> knownSequences, ref bool hasErrors)
    {
        AddSequenceList(asset, asset.startsSequences, "startsSequences", assetPaths, knownSequences, ref hasErrors);
        AddSequenceList(asset, asset.endsSequences, "endsSequences", assetPaths, knownSequences, ref hasErrors);
    }

    private static void AddSequenceList(SystemEvent asset, List<string> sequences, string listName, Dictionary<SystemEvent, string> assetPaths, HashSet<string> knownSequences, ref bool hasErrors)
    {
        if (sequences == null)
        {
            return;
        }

        HashSet<string> local = new HashSet<string>();
        foreach (string sequence in sequences)
        {
            string normalized = NormalizeToken(sequence);
            if (string.IsNullOrEmpty(normalized))
            {
                LogValidationError(asset, assetPaths, $"{listName} contains an empty sequence name.");
                hasErrors = true;
                continue;
            }

            string trimmed = sequence == null ? string.Empty : sequence.Trim();
            if (normalized != trimmed)
            {
                LogValidationWarning(asset, assetPaths, $"{listName} sequence '{trimmed}' will be normalized to '{normalized}'.");
            }

            if (!local.Add(normalized))
            {
                LogValidationError(asset, assetPaths, $"{listName} contains duplicate sequence name '{sequence}'.");
                hasErrors = true;
            }

            knownSequences.Add(normalized);
        }
    }

    private static void ValidateRequiredSequences(SystemEvent asset, Dictionary<SystemEvent, string> assetPaths, HashSet<string> knownSequences, ref bool hasErrors)
    {
        if (asset.requiresSequences == null)
        {
            return;
        }

        HashSet<string> local = new HashSet<string>();
        foreach (string sequence in asset.requiresSequences)
        {
            string normalized = NormalizeToken(sequence);
            if (string.IsNullOrEmpty(normalized))
            {
                LogValidationError(asset, assetPaths, "requiresSequences contains an empty sequence name.");
                hasErrors = true;
                continue;
            }

            string trimmed = sequence == null ? string.Empty : sequence.Trim();
            if (normalized != trimmed)
            {
                LogValidationWarning(asset, assetPaths, $"requiresSequences sequence '{trimmed}' will be normalized to '{normalized}'.");
            }

            if (!local.Add(normalized))
            {
                LogValidationError(asset, assetPaths, $"requiresSequences contains duplicate sequence name '{sequence}'.");
                hasErrors = true;
            }

            if (!knownSequences.Contains(normalized))
            {
                string suggestion = FindClosestSequence(normalized, knownSequences);
                string hint = string.IsNullOrEmpty(suggestion) ? "" : $" Did you mean '{suggestion}'?";
                LogValidationError(asset, assetPaths, $"requiresSequences references unknown sequence '{sequence}'.{hint}");
                hasErrors = true;
            }
        }
    }

    private static void ValidateConditions(SystemEvent asset, Dictionary<SystemEvent, string> assetPaths)
    {
        if (asset.conditions == null)
        {
            return;
        }

        foreach (var condition in asset.conditions)
        {
            string scopeNormalized = NormalizeToken(condition.scope);
            string scopeTrimmed = condition.scope == null ? string.Empty : condition.scope.Trim();
            if (!string.IsNullOrEmpty(scopeNormalized) && scopeNormalized != scopeTrimmed)
            {
                LogValidationWarning(asset, assetPaths, $"Condition scope '{scopeTrimmed}' will be normalized to '{scopeNormalized}'.");
            }

            string nameNormalized = NormalizeToken(condition.name);
            string nameTrimmed = condition.name == null ? string.Empty : condition.name.Trim();
            if (!string.IsNullOrEmpty(nameNormalized) && nameNormalized != nameTrimmed)
            {
                LogValidationWarning(asset, assetPaths, $"Condition name '{nameTrimmed}' will be normalized to '{nameNormalized}'.");
            }
        }
    }

    private static void ValidateMutations(SystemEvent asset, Dictionary<SystemEvent, string> assetPaths, ref bool hasErrors)
    {
        if (asset.mutates == null)
        {
            return;
        }

        foreach (Mutation mutation in asset.mutates)
        {
            string scopeNormalized = NormalizeToken(mutation.scope);
            string scopeTrimmed = mutation.scope == null ? string.Empty : mutation.scope.Trim();
            if (!string.IsNullOrEmpty(scopeNormalized) && scopeNormalized != scopeTrimmed)
            {
                LogValidationWarning(asset, assetPaths, $"Mutation scope '{scopeTrimmed}' will be normalized to '{scopeNormalized}'.");
            }

            string nameNormalized = NormalizeToken(mutation.name);
            string nameTrimmed = mutation.name == null ? string.Empty : mutation.name.Trim();
            if (!string.IsNullOrEmpty(nameNormalized) && nameNormalized != nameTrimmed)
            {
                LogValidationWarning(asset, assetPaths, $"Mutation name '{nameTrimmed}' will be normalized to '{nameNormalized}'.");
            }

            if (mutation.mutationType == MutationType.Delta)
            {
                if (!string.IsNullOrWhiteSpace(mutation.state))
                {
                    LogValidationError(asset, assetPaths, $"Mutation '{mutation.scope}.{mutation.name}' is Delta but has a state value '{mutation.state}'.");
                    hasErrors = true;
                }
            }
            else
            {
                if (mutation.delta != 0)
                {
                    LogValidationError(asset, assetPaths, $"Mutation '{mutation.scope}.{mutation.name}' is SetState but has a non-zero delta '{mutation.delta}'.");
                    hasErrors = true;
                }

                if (string.IsNullOrWhiteSpace(mutation.state))
                {
                    LogValidationError(asset, assetPaths, $"Mutation '{mutation.scope}.{mutation.name}' is SetState but has an empty state value.");
                    hasErrors = true;
                }
            }
        }
    }

    private static string NormalizeToken(string value)
    {
        return string.IsNullOrWhiteSpace(value) ? string.Empty : value.Trim().ToLower();
    }

    private static string FindClosestSequence(string normalizedSequence, HashSet<string> knownSequences)
    {
        const int maxDistance = 2;
        string best = null;
        int bestDistance = maxDistance + 1;

        foreach (string candidate in knownSequences)
        {
            int distance = LevenshteinDistance(normalizedSequence, candidate);
            if (distance < bestDistance)
            {
                bestDistance = distance;
                best = candidate;
            }
        }

        return bestDistance <= maxDistance ? best : null;
    }

    private static int LevenshteinDistance(string a, string b)
    {
        if (a == b)
        {
            return 0;
        }

        if (string.IsNullOrEmpty(a))
        {
            return string.IsNullOrEmpty(b) ? 0 : b.Length;
        }

        if (string.IsNullOrEmpty(b))
        {
            return a.Length;
        }

        int[,] distances = new int[a.Length + 1, b.Length + 1];

        for (int i = 0; i <= a.Length; i++)
        {
            distances[i, 0] = i;
        }

        for (int j = 0; j <= b.Length; j++)
        {
            distances[0, j] = j;
        }

        for (int i = 1; i <= a.Length; i++)
        {
            for (int j = 1; j <= b.Length; j++)
            {
                int cost = a[i - 1] == b[j - 1] ? 0 : 1;
                int deletion = distances[i - 1, j] + 1;
                int insertion = distances[i, j - 1] + 1;
                int substitution = distances[i - 1, j - 1] + cost;
                distances[i, j] = Mathf.Min(deletion, Mathf.Min(insertion, substitution));
            }
        }

        return distances[a.Length, b.Length];
    }

    private static string GetPath(SystemEvent asset, Dictionary<SystemEvent, string> assetPaths)
    {
        return assetPaths.TryGetValue(asset, out string path) ? path : "(unknown path)";
    }

    private static void LogValidationWarning(SystemEvent asset, Dictionary<SystemEvent, string> assetPaths, string message)
    {
        string id = string.IsNullOrWhiteSpace(asset.eventID) ? "(missing eventID)" : asset.eventID;
        Debug.LogWarning($"[SystemEvent Validation] {message} EventID='{id}' Path='{GetPath(asset, assetPaths)}'");
    }

    private static void LogValidationError(SystemEvent asset, Dictionary<SystemEvent, string> assetPaths, string message)
    {
        string id = string.IsNullOrWhiteSpace(asset.eventID) ? "(missing eventID)" : asset.eventID;
        Debug.LogError($"[SystemEvent Validation] {message} EventID='{id}' Path='{GetPath(asset, assetPaths)}'");
    }

    private static List<string> NormalizeList(List<string> input)
    {
        List<string> normalized = new List<string>();
        if (input == null)
        {
            return normalized;
        }

        HashSet<string> unique = new HashSet<string>();
        foreach (string value in input)
        {
            string token = NormalizeToken(value);
            if (!string.IsNullOrEmpty(token) && unique.Add(token))
            {
                normalized.Add(token);
            }
        }

        return normalized;
    }
}
