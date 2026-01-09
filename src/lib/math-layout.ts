
// Helper to apply default class to keys
const k = (items: any[]) => items.map(item => ({ class: "key-cap", ...item }));

// Common Navigation Row (Layer Switchers)
const NAV_ROW = [
    { label: "Basic", class: "w-15 key-cap", command: ["switchKeyboardLayer", "basic"], layer: "basic" },
    { label: "αβγ", class: "w-15 key-cap", command: ["switchKeyboardLayer", "greek-small"], layer: "greek-small" },
    { label: "ABΓ", class: "w-15 key-cap", command: ["switchKeyboardLayer", "greek-large"], layer: "greek-large" },
    { label: "sin cos", class: "w-15 key-cap", command: ["switchKeyboardLayer", "trig"], layer: "trig" },
    { label: "≥ ÷ →", class: "w-15 key-cap", command: ["switchKeyboardLayer", "operators"], layer: "operators" },
    { label: "x̅ ℂ ∀", class: "w-15 key-cap", command: ["switchKeyboardLayer", "accents"], layer: "accents" },
    { label: "Σ ∫ Π", class: "w-15 key-cap", command: ["switchKeyboardLayer", "big-operators"], layer: "big-operators" },
    { label: "( ▪ ▪ )", class: "w-15 key-cap", command: ["switchKeyboardLayer", "matrix"], layer: "matrix" },
    { label: "H₂O", class: "w-15 key-cap", command: ["switchKeyboardLayer", "chemistry"], layer: "chemistry" },
    { label: "⌨", class: "w-15 key-cap", command: ["switchKeyboardLayer", "calculator"], layer: "calculator" }
];

// Helper to set active tab style
const getNavRow = (activeLayerId: string) => {
    return NAV_ROW.map(key => ({
        ...key,
        class: key.layer === activeLayerId ? "w-15 key-cap active" : "w-15 key-cap"
    }));
};

// Common Functions Row (Shared across most layers)
const COMMON_FUNC_ROW = k([
    { latex: "^{2}", label: "□²" },
    { latex: "^{#?}", label: "x^□" },
    { latex: "\\sqrt{#0}", label: "√□" },
    { latex: "\\sqrt[#0]{#?}", label: "ⁿ√□" },
    { latex: "\\frac{#0}{#?}", label: "□/□" },
    { latex: "\\log_{#?}(#0)", label: "log_□" },
    { latex: "\\pi", label: "π" },
    { latex: "\\theta", label: "θ" },
    { latex: "\\infty", label: "∞" },
    { latex: "\\int", label: "∫" },
    { latex: "\\frac{d}{dx}", label: "d/dx" }
]);

export const CUSTOM_KEYBOARD_LAYOUT = {
    name: "custom",
    layers: [
        {
            id: "basic",
            rows: [
                getNavRow("basic"),
                k([
                    { latex: "\\ge", label: "≥" },
                    { latex: "\\le", label: "≤" },
                    { latex: "\\cdot", label: "·" },
                    { latex: "\\div", label: "÷" },
                    { latex: "^{\\circ}", label: "°" },
                    { latex: "(#0)", label: "(□)" },
                    { latex: "|#0|", label: "|□|" },
                    { insert: "f(x)", label: "f(x)" },
                    { latex: "\\ln(#0)", label: "ln" },
                    { latex: "e^{#?}", label: "e^□" },
                ]),
                k([
                    { latex: "(#0)'", label: "(□)'" },
                    { latex: "\\frac{\\partial}{\\partial x}", label: "∂/∂x" },
                    { latex: "\\int_{#?}^{#?}", label: "∫_□^□" },
                    { latex: "\\lim_{x\\to\\infty}", label: "lim" },
                    { latex: "\\sum_{n=0}^{\\infty}", label: "Σ" },
                    { latex: "\\sin", label: "sin" },
                    { latex: "\\cos", label: "cos" },
                    { latex: "\\tan", label: "tan" },
                    { latex: "\\cot", label: "cot" },
                    { latex: "\\csc", label: "csc" },
                    { latex: "\\sec", label: "sec" }
                ]),
                [
                    { class: "action key-cap", command: ["performWithFeedback", "deleteBackward"], label: "⌫" },
                    { class: "action key-cap", command: ["performWithFeedback", "commit"], label: "Enter" }
                ]
            ]
        },
        {
            id: "greek-small",
            rows: [
                getNavRow("greek-small"),
                COMMON_FUNC_ROW,
                k([
                    { latex: "\\alpha" }, { latex: "\\beta" }, { latex: "\\gamma" }, { latex: "\\delta" }, { latex: "\\zeta" }, { latex: "\\eta" }, { latex: "\\theta" }, { latex: "\\iota" }, { latex: "\\kappa" }, { latex: "\\lambda" }, { latex: "\\mu" }
                ]),
                k([
                    { latex: "\\nu" }, { latex: "\\xi" }, { latex: "\\pi" }, { latex: "\\rho" }, { latex: "\\sigma" }, { latex: "\\tau" }, { latex: "\\upsilon" }, { latex: "\\phi" }, { latex: "\\chi" }, { latex: "\\psi" }, { latex: "\\omega" }
                ]),
                [
                    { class: "action key-cap", command: ["performWithFeedback", "deleteBackward"], label: "⌫" },
                    { class: "action key-cap", command: ["performWithFeedback", "commit"], label: "Enter" }
                ]
            ]
        },
        {
            id: "greek-large",
            rows: [
                getNavRow("greek-large"),
                COMMON_FUNC_ROW,
                k([
                    { latex: "A" }, { latex: "B" }, { latex: "\\Gamma" }, { latex: "\\Delta" }, { latex: "E" }, { latex: "Z" }, { latex: "H" }, { latex: "\\Theta" }, { latex: "K" }, { latex: "\\Lambda" }, { latex: "M" }
                ]),
                k([
                    { latex: "N" }, { latex: "\\Xi" }, { latex: "\\Pi" }, { latex: "P" }, { latex: "\\Sigma" }, { latex: "T" }, { latex: "\\Upsilon" }, { latex: "\\Phi" }, { latex: "X" }, { latex: "\\Psi" }, { latex: "\\Omega" }
                ]),
                [
                    { class: "action key-cap", command: ["performWithFeedback", "deleteBackward"], label: "⌫" },
                    { class: "action key-cap", command: ["performWithFeedback", "commit"], label: "Enter" }
                ]
            ]
        },
        {
            id: "trig",
            rows: [
                getNavRow("trig"),
                COMMON_FUNC_ROW,
                k([
                    { latex: "\\sin" }, { latex: "\\cos" }, { latex: "\\tan" }, { latex: "\\cot" }, { latex: "\\sec" }, { latex: "\\csc" },
                    { latex: "\\sinh" }, { latex: "\\cosh" }, { latex: "\\tanh" }, { latex: "\\coth" }, { latex: "\\sech" }
                ]),
                k([
                    { latex: "\\arcsin" }, { latex: "\\arccos" }, { latex: "\\arctan" }, { latex: "\\text{arccot}" }, { latex: "\\text{arcsec}" }, { latex: "\\text{arccsc}" },
                    { latex: "\\text{arcsinh}" }, { latex: "\\text{arccosh}" }, { latex: "\\text{arctanh}" }, { latex: "\\text{arccoth}" }, { latex: "\\text{arcsech}" }
                ]),
                [
                    { class: "action key-cap", command: ["performWithFeedback", "deleteBackward"], label: "⌫" },
                    { class: "action key-cap", command: ["performWithFeedback", "commit"], label: "Enter" }
                ]
            ]
        },
        {
            id: "operators",
            rows: [
                getNavRow("operators"),
                k([
                    { latex: "\\begin{cases} & \\\\ & \\end{cases}", label: "cases 2" },
                    { latex: "\\begin{cases} & \\\\ & \\\\ & \\end{cases}", label: "cases 3" },
                    { latex: "=" }, { latex: "\\ne" }, { latex: "\\div" }, { latex: "\\cdot" }, { latex: "\\times" }, { latex: "<" }, { latex: ">" }, { latex: "\\le" }, { latex: "\\ge" }
                ]),
                k([
                    { latex: "(#0)", label: "(□)" }, { latex: "[#0]", label: "[□]" },
                    { latex: "!", label: "!" }, { latex: "^{\\circ}", label: "°" }, { latex: "\\rightarrow", label: "→" },
                    { latex: "\\lfloor#0\\rfloor", label: "⌊□⌋" }, { latex: "\\lceil#0\\rceil", label: "⌈□⌉" }
                ]),
                [
                    { class: "action key-cap", command: ["performWithFeedback", "deleteBackward"], label: "⌫" },
                    { class: "action key-cap", command: ["performWithFeedback", "commit"], label: "Enter" }
                ]
            ]
        },
        {
            id: "accents",
            rows: [
                getNavRow("accents"),
                COMMON_FUNC_ROW,
                k([
                    { latex: "\\overline{#0}", label: "͞□" }, { latex: "\\vec{#0}", label: "→□" },
                    { latex: "\\in", label: "∈" }, { latex: "\\forall", label: "∀" }, { latex: "\\notin", label: "∉" }, { latex: "\\exists", label: "∃" },
                    { latex: "\\mathbb{R}", label: "ℝ" }, { latex: "\\mathbb{C}", label: "ℂ" }, { latex: "\\mathbb{N}", label: "ℕ" }, { latex: "\\mathbb{Z}", label: "ℤ" }, { latex: "\\emptyset", label: "∅" }
                ]),
                k([
                    { latex: "\\vee", label: "∨" }, { latex: "\\wedge", label: "∧" }, { latex: "\\neg", label: "¬" }, { latex: "\\oplus", label: "⊕" },
                    { latex: "\\cap", label: "∩" }, { latex: "\\cup", label: "∪" }, { latex: "^{c}", label: "□ᶜ" },
                    { latex: "\\subset", label: "⊂" }, { latex: "\\subseteq", label: "⊆" }, { latex: "\\supset", label: "⊃" }, { latex: "\\supseteq", label: "⊇" }
                ]),
                [
                    { class: "action key-cap", command: ["performWithFeedback", "deleteBackward"], label: "⌫" },
                    { class: "action key-cap", command: ["performWithFeedback", "commit"], label: "Enter" }
                ]
            ]
        },
        {
            id: "big-operators",
            rows: [
                getNavRow("big-operators"),
                k([
                    { latex: "\\int", label: "∫" }, { latex: "\\iint", label: "∬" }, { latex: "\\iiint", label: "∭" },
                    { latex: "\\int_{#?}^{#?}", label: "∫□" }, { latex: "\\iint_{#?}^{#?}", label: "∬□" }, { latex: "\\iiint_{#?}^{#?}", label: "∭□" },
                    { latex: "\\sum", label: "Σ" }, { latex: "\\prod", label: "Π" }
                ]),
                k([
                    { latex: "\\lim_{x\\to#?}", label: "lim→" }, { latex: "\\lim_{x\\to\\infty}", label: "lim∞" },
                    { latex: "\\frac{d}{dx}", label: "d/dx" }, { latex: "\\frac{d^2}{dx^2}", label: "d²/dx²" },
                    { latex: "(#0)'", label: "□'" }, { latex: "(#0)''", label: "□''" },
                    { latex: "\\frac{\\partial}{\\partial x}", label: "∂/∂x" }
                ]),
                [
                    { class: "action key-cap", command: ["performWithFeedback", "deleteBackward"], label: "⌫" },
                    { class: "action key-cap", command: ["performWithFeedback", "commit"], label: "Enter" }
                ]
            ]
        },
        {
            id: "matrix",
            rows: [
                getNavRow("matrix"),
                COMMON_FUNC_ROW,
                k([
                    { latex: "\\begin{pmatrix}\\square & \\square \\\\ \\square & \\square\\end{pmatrix}", label: "2x2" },
                    { latex: "\\begin{pmatrix}\\square & \\square & \\square \\\\ \\square & \\square & \\square \\\\ \\square & \\square & \\square\\end{pmatrix}", label: "3x3" },
                    { latex: "\\begin{pmatrix}\\square \\\\ \\square\\end{pmatrix}", label: "2x1" },
                    { latex: "\\begin{pmatrix}\\square & \\square\\end{pmatrix}", label: "1x2" },
                    { latex: "\\begin{pmatrix}\\square & \\square & \\square\\end{pmatrix}", label: "1x3" },
                    { latex: "\\begin{pmatrix}\\square \\\\ \\square \\\\ \\square\\end{pmatrix}", label: "3x1" }
                ]),
                k([
                    { latex: "\\det", label: "det" },
                    { latex: "^T", label: "T" },
                    { latex: "\\begin{pmatrix}\\square & \\square \\\\ \\square & \\square \\\\ \\square & \\square\\end{pmatrix}", label: "3x2" },
                    { latex: "\\begin{pmatrix}\\square & \\square & \\square & \\square\\end{pmatrix}", label: "1x4" }
                ]),
                [
                    { class: "action key-cap", command: ["performWithFeedback", "deleteBackward"], label: "⌫" },
                    { class: "action key-cap", command: ["performWithFeedback", "commit"], label: "Enter" }
                ]
            ]
        },
        {
            id: "chemistry",
            rows: [
                getNavRow("chemistry"),
                // Row 1: H ... He
                k([{ latex: "H" }, { gap: "16" }, { latex: "He" }]),
                // Row 2: Li, Be ... B, C, N, O, F, Ne
                k([{ latex: "Li" }, { latex: "Be" }, { gap: "10" }, { latex: "B" }, { latex: "C" }, { latex: "N" }, { latex: "O" }, { latex: "F" }, { latex: "Ne" }]),
                // Row 3: Na, Mg ... Al, Si, P, S, Cl, Ar
                k([{ latex: "Na" }, { latex: "Mg" }, { gap: "10" }, { latex: "Al" }, { latex: "Si" }, { latex: "P" }, { latex: "S" }, { latex: "Cl" }, { latex: "Ar" }]),
                // Row 4: K ... Kr
                k([{ latex: "K" }, { latex: "Ca" }, { latex: "Sc" }, { latex: "Ti" }, { latex: "V" }, { latex: "Cr" }, { latex: "Mn" }, { latex: "Fe" }, { latex: "Co" }, { latex: "Ni" }, { latex: "Cu" }, { latex: "Zn" }, { latex: "Ga" }, { latex: "Ge" }, { latex: "As" }, { latex: "Se" }, { latex: "Br" }, { latex: "Kr" }]),
                // Row 5: Rb ... Xe
                k([{ latex: "Rb" }, { latex: "Sr" }, { latex: "Y" }, { latex: "Zr" }, { latex: "Nb" }, { latex: "Mo" }, { latex: "Tc" }, { latex: "Ru" }, { latex: "Rh" }, { latex: "Pd" }, { latex: "Ag" }, { latex: "Cd" }, { latex: "In" }, { latex: "Sn" }, { latex: "Sb" }, { latex: "Te" }, { latex: "I" }, { latex: "Xe" }]),
                // Row 6: Cs ... Rn
                k([{ latex: "Cs" }, { latex: "Ba" }, { gap: "1" }, { latex: "Hf" }, { latex: "Ta" }, { latex: "W" }, { latex: "Re" }, { latex: "Os" }, { latex: "Ir" }, { latex: "Pt" }, { latex: "Au" }, { latex: "Hg" }, { latex: "Tl" }, { latex: "Pb" }, { latex: "Bi" }, { latex: "Po" }, { latex: "At" }, { latex: "Rn" }]),
                // Row 7: Fr ... Og
                k([{ latex: "Fr" }, { latex: "Ra" }, { gap: "1" }, { latex: "Rf" }, { latex: "Db" }, { latex: "Sg" }, { latex: "Bh" }, { latex: "Hs" }, { latex: "Mt" }, { latex: "Ds" }, { latex: "Rg" }, { latex: "Cn" }, { latex: "Nh" }, { latex: "Fl" }, { latex: "Mc" }, { latex: "Lv" }, { latex: "Ts" }, { latex: "Og" }]),
                // Spacer
                k([{ gap: "1" }]),
                // Row 8: Lanthanides
                k([{ gap: "3" }, { latex: "La" }, { latex: "Ce" }, { latex: "Pr" }, { latex: "Nd" }, { latex: "Pm" }, { latex: "Sm" }, { latex: "Eu" }, { latex: "Gd" }, { latex: "Tb" }, { latex: "Dy" }, { latex: "Ho" }, { latex: "Er" }, { latex: "Tm" }, { latex: "Yb" }, { latex: "Lu" }]),
                // Row 9: Actinides
                k([{ gap: "3" }, { latex: "Ac" }, { latex: "Th" }, { latex: "Pa" }, { latex: "U" }, { latex: "Np" }, { latex: "Pu" }, { latex: "Am" }, { latex: "Cm" }, { latex: "Bk" }, { latex: "Cf" }, { latex: "Es" }, { latex: "Fm" }, { latex: "Md" }, { latex: "No" }, { latex: "Lr" }]),
                [
                    { class: "action key-cap", command: ["performWithFeedback", "deleteBackward"], label: "⌫" },
                    { class: "action key-cap", command: ["performWithFeedback", "commit"], label: "Enter" }
                ]
            ]
        },
        {
            id: "calculator",
            rows: [
                getNavRow("calculator"),
                k([
                    { latex: "\\arcsin", label: "asin" }, { latex: "\\sin", label: "sin" }, { latex: "\\sqrt{#0}", label: "√" }, { latex: "7" }, { latex: "8" }, { latex: "9" }, { latex: "\\div", label: "÷" }
                ]),
                k([
                    { latex: "\\arccos", label: "acos" }, { latex: "\\cos", label: "cos" }, { latex: "\\ln", label: "ln" }, { latex: "4" }, { latex: "5" }, { latex: "6" }, { latex: "\\times", label: "×" }
                ]),
                k([
                    { latex: "\\arctan", label: "atan" }, { latex: "\\tan", label: "tan" }, { latex: "\\log", label: "log" }, { latex: "1" }, { latex: "2" }, { latex: "3" }, { latex: "-", label: "-" }
                ]),
                k([
                    { latex: "\\pi", label: "π" }, { latex: "e", label: "e" }, { latex: "^", label: "^" }, { latex: "0" }, { latex: ".", label: "." }, { latex: "=", label: "=" }, { latex: "+", label: "+" }
                ]),
                [
                    { class: "action key-cap", command: ["performWithFeedback", "deleteBackward"], label: "⌫" },
                    { class: "action key-cap", command: ["performWithFeedback", "commit"], label: "Enter" }
                ]
            ]
        }
    ]
};
