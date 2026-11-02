# Atavism — Research Charter

## Project Identity

**Name:** Atavism
**Focus:** Contract Intelligence and Specification Adherence in LLM-Based Software Engineering

## Central Research Question

Can AI coding models reliably interpret and implement explicit software contracts when those contracts differ from familiar programming conventions?

## Motivation

AI coding models can produce functional-looking code that quietly violates explicit requirements. In professional software engineering, correct behavior is defined by the contract—not by what is conventional. A provider may define non-standard retry semantics, an API may use unusual event-stream behavior, or versioned documentation may contain requirements that override common assumptions.

We aim to measure whether models follow the specification they are given or default to familiar patterns.

## Methodology

Atavism uses **controlled, paired benchmark tasks**:

- **Control (A):** A task variant containing conventional behavior.
- **Treatment (B):** A task variant containing an explicitly documented deviation from convention.
- Both variants share the same implementation requirements, starter code, and grading logic (except for the intentional difference).
- We compare model outputs to identify specification-adherence failures.

This paired design isolates the effect of specification deviations from general coding ability.

## Research Dimensions

| Dimension | Evaluates |
|---|---|
| Convention Divergence | Following explicit behavior that differs from familiar conventions |
| Specification Conflict Resolution | Identifying authoritative requirements when documentation conflicts |
| Semantic Composition | Preserving multiple interacting technical requirements |
| Uncertainty Handling | Recognizing incomplete or contradictory specifications |
| Contract Consistency | Maintaining specified behavior throughout an implementation |

## Scope and Limitations

- Atavism is an evaluation benchmark, not a product, chatbot, or agent.
- All API providers and scenarios are synthetic.
- Results reflect model behavior on controlled tasks and should not be generalized without qualification.
- The benchmark does not attempt to create trick questions—all requirements are explicitly stated in each task's contract.

## Ethical Considerations

- No real user data is collected or processed.
- Model outputs are evaluated programmatically; no human subjects are involved.
- We report limitations honestly and avoid overstating findings.
