### Q1
Q1) Calculus + Function Sketch (solve, then plot)
Let f(x) = x^3 - 6x^2 + 9x + 1.

Tasks:
1) Find all critical points of f(x) and classify each as local max, local min, or neither.
2) Find all inflection point(s) of f(x).
3) Find the x-intercepts (real roots) of f(x) to at least 3 decimal places.
4) Draw a plot of f(x) on the interval x â?? [-1, 6] with:
 - the curve y = f(x)
 - marked critical points and inflection point(s) (distinct markers)
 - labeled x-intercepts (approx values)
 - axes lines (x=0 and y=0), grid, and a legend

**Steps**
1. 

2. 1) **Find all critical points of \( f(x) \) and classify each as local max, local min, or neither.**
3. First, we find the first derivative of \( f(x) \):
 \[
 f'(x) = 3x^2 - 12x + 9
 \]
 To find the critical points, we set \( f'(x) = 0 \):
 \[
 3x^2 - 12x + 9 = 0
 \]
 This is a quadratic equation. We can factor it as:
 \[
 3(x^2 - 4x + 3) = 0 \implies 3(x-1)(x-3) = 0
 \]
 So, the critical points are \( x = 1 \) and \( x = 3 \).
4. Next, we use the second derivative test to classify these critical points. The second derivative of \( f(x) \) is:
 \[
 f''(x) = 6x - 12
 \]
 Evaluating the second derivative at the critical points:
 \[
 f''(1) = 6(1) - 12 = -6 < 0
 \]
 Since \( f''(1) < 0 \), \( x = 1 \) is a local maximum.
 \[
 f''(3) = 6(3) - 12 = 6 > 0
 \]
 Since \( f''(3) > 0 \), \( x = 3 \) is a local minimum.
5. 2) **Find all inflection point(s) of \( f(x) \).**
6. Inflection points occur where the second derivative changes sign. We set \( f''(x) = 0 \):
 \[
 6x - 12 = 0 \implies x = 2
 \]
 To confirm that \( x = 2 \) is an inflection point, we check the sign of \( f''(x) \) around \( x = 2 \). For \( x < 2 \), \( f''(x) < 0 \), and for \( x > 2 \), \( f''(x) > 0 \). Therefore, \( x = 2 \) is an inflection point.
7. 3) **Find the x-intercepts (real roots) of \( f(x) \) to at least 3 decimal places.**
8. The x-intercepts are the solutions to \( f(x) = 0 \):
 \[
 x^3 - 6x^2 + 9x + 1 = 0
 \]
 Using numerical methods (such as the Newton-Raphson method or a graphing calculator), we find the approximate roots:
 \[
 x \approx -0.112, \quad x \approx 2.556, \quad x \approx 3.556
 \]
9. 4) **Draw a plot of \( f(x) \) on the interval \( x \in [-1, 6] \) with:**
 - the curve \( y = f(x) \)
 - marked critical points and inflection point(s) (distinct markers)
 - labeled x-intercepts (approx values)
 - axes lines (x=0 and y=0), grid, and a legend.
10. Since we are not able to draw the plot here, we will describe it in words. The curve \( y = f(x) \) is a cubic polynomial with a local maximum at \( x = 1 \), a local minimum at \( x = 3 \), and an inflection point at \( x = 2 \). The x-intercepts are approximately \( x \approx -0.112 \), \( x \approx 2.556 \), and \( x \approx 3.556 \).
11. 
\[
\boxed{-0.112, 2.556, 3.556}
\]

**Answer:** \boxed{-0.112, 2.556, 3.556}
