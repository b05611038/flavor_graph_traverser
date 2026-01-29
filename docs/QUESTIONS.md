# Question Templates

## Category A: Taxonomic Reasoning (180 questions)

### A1: Root Classification (50 questions)

```
Question: Which root category does 'jasmine' belong to?
(A) fruity  (B) floral  (C) sweet  (D) spicy

Answer: (B)
```

### A2: Ancestor Verification (50 questions)

```
Question: Is 'rose' a descendant of 'floral'?
(A) Yes  (B) No

Answer: (A)
```

### A3: Sibling Identification (30 questions)

```
Question: Which shares the same parent as 'jasmine'?
(A) rose  (B) strawberry  (C) caramel  (D) pepper

Answer: (A)
```

### A4: Path Reconstruction (30 questions)

```
Question: What is the path from 'strawberry' to its root?
(A) strawberry → berry → fruity
(B) strawberry → fruity
(C) strawberry → red_fruit → fruity
(D) strawberry → sweet → fruity

Answer: (A)
```

### A5: Lowest Common Ancestor (20 questions)

```
Question: What is the most specific category containing both 'jasmine' and 'rose'?
(A) floral  (B) inner_floral  (C) middle_floral  (D) root

Answer: (C)
```

## Category E: Similarity Reasoning (80 questions)

### E1: Similarity Ranking (30 questions)

```
Question: Rank by similarity to 'strawberry': berry, citrus, cocoa
(A) berry > citrus > cocoa
(B) citrus > berry > cocoa
(C) cocoa > berry > citrus
(D) berry > cocoa > citrus

Answer: (A)
```

### E2: Pairwise Comparison (30 questions)

```
Question: Which is more similar to 'honey': caramel or lemon?
(A) caramel  (B) lemon

Answer: (A)
```

### E3: Odd One Out (20 questions)

```
Question: Which does NOT belong: jasmine, rose, chamomile, walnut?
(A) jasmine  (B) rose  (C) chamomile  (D) walnut

Answer: (D)
```

## Category F: Open Reasoning (15 questions, LLM-judged)

```
Question: A customer enjoys 'berry' flavors but wants to explore 
something new. Using the flavor hierarchy, suggest alternatives 
and explain your reasoning.

Evaluation Rubric (1-5 scale):
- Relevance: Are suggestions related in the hierarchy?
- Reasoning: Is the justification logical?
- Specificity: Are concrete descriptors mentioned?
- Coherence: Do recommendations form a unified profile?
```

## Answer Format

All multiple choice questions expect:
```
"Therefore, I select (X)." where X is A, B, C, or D.
```
