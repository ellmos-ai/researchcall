# Eigene Policy — Vorlage

> Kopieren, umbenennen, ausfuellen. Eine Policy ist eine Regel, die der Nutzer setzt und
> die der Agent in jedem betroffenen Schritt befolgt.

```yaml
name: <kurzer-name>
applies_to: [ 02-instrument, 03-ethics ]   # Stationen, oder "all"
priority: normal                            # normal | high | absolute
```

## Was diese Policy verlangt

<Ein bis drei Saetze im Imperativ. Was soll immer geschehen?>

## Was sie verbietet

<Was darf nie geschehen? Absolute Verbote hier, nicht im Fliesstext.>

## Warum

<Der Grund. Ohne ihn kann der Agent nicht abwaegen, wenn zwei Policies kollidieren.>

## Beispiele

**Richtig:** <ein Fall>
**Falsch:** <ein Fall, der wie richtig aussieht, aber falsch ist>
