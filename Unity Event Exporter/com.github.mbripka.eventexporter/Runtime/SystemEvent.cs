using UnityEngine;
using System.Collections.Generic;

public enum ComparisonOperator
{
    LessThan,
    GreaterThan,
    Equal,
    GreaterThanOrEqual,
    LessThanOrEqual
}

public enum MutationType
{
    Delta,
    SetState
}

public enum ValueType
{
    Int,
    State
}

[System.Serializable]
public class Condition
{
    public string scope;
    public string name;
    public ComparisonOperator comparisonOperator;

    public ValueType valueType;
    public int intValue;
    public string stateValue;
}

[System.Serializable]
public class Mutation
{
    public string scope;
    public string name;
    public MutationType mutationType;

    public int delta;
    public string state;
}

[CreateAssetMenu(menuName = "Events/System Event")]
public class SystemEvent : ScriptableObject
{
    public string eventID;
    public string eventName;
    public int maxTriggers = -1;

    // Sequences
    public List<string> requiresSequences = new List<string>();
    public List<string> startsSequences = new List<string>();
    public List<string> endsSequences = new List<string>();

    // Logic
    public List<Condition> conditions = new List<Condition>();
    public List<Mutation> mutates = new List<Mutation>();

    // Optional
    public List<string> tags = new List<string>();
}