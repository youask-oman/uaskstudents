"use client";

import React, { useEffect, useRef, useImperativeHandle, forwardRef, useState } from 'react';
import { CUSTOM_KEYBOARD_LAYOUT } from '@/lib/math-layout';
import 'mathlive/static.css';
import type { MathfieldElement } from 'mathlive';
import { useTheme } from '@/hooks/useTheme';

interface MathInputProps {
    value: string;
    onChange: (latex: string) => void;
    placeholder?: string;
    onEnter?: () => void;
    className?: string;
    maxLength?: number;
    onPaste?: (pastedText: string) => void;
}

export interface MathInputRef {
    insert: (latex: string) => void;
    focus: () => void;
    setValue: (latex: string) => void;
    getValue: () => string;
}

const MathInput = forwardRef<MathInputRef, MathInputProps>(({ value, onChange, placeholder, onEnter, className = "", maxLength, onPaste }, ref) => {
    const mfRef = useRef<MathfieldElement | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const isInternalChange = useRef(false);

    const { isDark } = useTheme();
    const [mounted, setMounted] = useState(false);

    const kbBg: string = '#ffffff';

    useEffect(() => {
        setMounted(true);
        // Dynamically import mathlive to avoid SSR issues
        import('mathlive').then(() => {
            // Apply custom keyboard layout
            // Apply custom keyboard layout
            if (window.mathVirtualKeyboard) {
                console.log("Applying custom keyboard layout:", CUSTOM_KEYBOARD_LAYOUT);

                try {
                    // mathVirtualKeyboard.layouts expects an array of VirtualKeyboardLayout
                    window.mathVirtualKeyboard.layouts = [
                        CUSTOM_KEYBOARD_LAYOUT,
                    ];
                    console.log("Layout applied successfully");
                } catch (e) {
                    console.error("Error applying layout:", e);
                }
                // Make our custom layout the default
                // We don't set 'visible' to false here to allow 'auto' policy to work naturally
            }

            // Ensure the custom element is defined
            if (!customElements.get('math-field')) {
                // It registers itself automatically upon import usually
            }
        });
    }, []);

    const readMathFieldValue = (target: MathfieldElement | null): string => {
        if (target && typeof target.getValue === "function") {
            const latex = target.getValue();
            if (typeof latex === "string") return latex;
        }
        if (typeof target?.value === "string") return target.value;
        return String(target?.value ?? "");
    };

    useImperativeHandle(ref, () => ({
        insert: (latex: string) => {
            const mf = mfRef.current;
            if (mf) {
                mf.executeCommand(['insert', latex]);
                mf.focus();
            }
        },
        focus: () => {
            const mf = mfRef.current;
            if (mf) {
                mf.focus();
            }
        },
        setValue: (latex: string) => {
            const mf = mfRef.current;
            if (mf) {
                mf.setValue(latex);
            }
        },
        getValue: () => {
            return readMathFieldValue(mfRef.current);
        }
    }));

    useEffect(() => {
        const mf = mfRef.current;
        if (!mf) return;

        const handleInput = (e: Event) => {
            isInternalChange.current = true;
            const nextValue = readMathFieldValue(e.target as MathfieldElement | null);
            onChange(nextValue);
            isInternalChange.current = false;
        };

        // Keydown handler for Enter
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                onEnter?.();
            }
        };

        // Paste handler for worksheet protection
        const handlePaste = (e: ClipboardEvent) => {
            const pastedText = e.clipboardData?.getData('text') || '';

            // Truncate if over maxLength
            if (maxLength && pastedText.length > maxLength) {
                e.preventDefault();
                const truncated = pastedText.slice(0, maxLength);
                mf.setValue(truncated);
                onChange(truncated);
            }

            // Call external paste handler
            onPaste?.(pastedText);
        };

        mf.addEventListener('input', handleInput);
        mf.addEventListener('keydown', handleKeyDown);
        mf.addEventListener('paste', handlePaste);

        return () => {
            mf.removeEventListener('input', handleInput);
            mf.removeEventListener('keydown', handleKeyDown);
            mf.removeEventListener('paste', handlePaste);
        };
    }, [onChange, onEnter, maxLength, onPaste]);

    // Sync external value changes
    useEffect(() => {
        const mf = mfRef.current;
        if (mf && mf.value !== value && !isInternalChange.current) {
            mf.value = value;
        }
    }, [value]);

    return (
        <div ref={containerRef} className={`math-input-container w-full ${className}`}>
            {/* MathField mounted here */}
            <style jsx global>{`
                math-field {
                    width: 100%;
                    background: transparent;
                    font-size: 1.1rem;
                    border: none;
                    outline: none;
                    padding: 8px;
                    min-height: 60px; /* Ensure space for multiline */
                    display: block;
                }
                math-field::part(content) {
                    white-space: pre-wrap !important;
                    word-break: break-word !important;
                    overflow-wrap: anywhere !important;
                    text-align: left;
                }

                /* Virtual Keyboard Theme Variables */
                :root {
                    --ml-keyboard-bg: ${kbBg};
                    --ml-keyboard-text: ${kbBg === '#ffffff' || kbBg.startsWith('rgba(255') ? '#1e293b' : '#ffffff'};
                    --ml-keyboard-border: ${kbBg === '#ffffff' || kbBg.startsWith('rgba(255') ? '#e2e8f0' : 'rgba(255,255,255,0.1)'};
                    --key-cap-active-background: #ef4444; 
                    --key-cap-active-text: white;
                }

                /* Target the MathLive virtual keyboard core */
                .ml-virtual-keyboard-layers {
                    background: var(--ml-keyboard-bg) !important;
                    color: var(--ml-keyboard-text) !important;
                    max-height: 260px !important; /* Force compact height */
                    overflow-y: auto !important;
                    backdrop-filter: blur(8px);
                    border-top: 1px solid var(--ml-keyboard-border);
                    box-shadow: 0 -8px 30px rgba(0, 0, 0, 0.12);
                    padding-bottom: 8px;
                }

                /* Global Key Styling */
                .key-cap {
                    background: ${kbBg === '#ffffff' || kbBg.startsWith('rgba(255') ? '#f1f5f9' : 'rgba(255,255,255,0.15)'} !important;
                    border: 1px solid var(--ml-keyboard-border) !important;
                    border-radius: 6px !important;
                    font-weight: 500 !important;
                    color: var(--ml-keyboard-text) !important;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: all 0.15s ease;
                    height: 32px !important;
                    min-width: 32px;
                    padding: 0 4px;
                    font-size: 0.85rem !important;
                }

                /* Active Tab (Red) */
                .key-cap.active {
                    background: #ef4444 !important;
                    color: white !important;
                    border-color: #ef4444 !important;
                    font-weight: 700 !important;
                }

                .key-cap:hover {
                    background: ${kbBg === '#ffffff' || kbBg.startsWith('rgba(255') ? '#e2e8f0' : 'rgba(255,255,255,0.25)'} !important;
                }

                .key-cap:active {
                    transform: scale(0.92);
                }

                /* Navigation Row Spacing */
                .w-15 {
                    min-width: 54px !important;
                    height: 34px !important;
                    font-size: 0.75rem !important;
                    margin: 0 2px;
                }

                /* Ensure the keyboard is scrollable if too wide */
                .ml-keyboard {
                    overflow-x: auto !important;
                    -webkit-overflow-scrolling: touch;
                }

                /* Periodic Table (Chemistry) Specific Key Tweaks */
                [id="chemistry"] .key-cap {
                    font-size: 0.65rem !important;
                    min-width: 24px;
                    height: 28px !important;
                    margin: 1px;
                }

                /* Hide the default backdrop if any */
                .ml-virtual-keyboard-backdrop {
                    display: none !important;
                }
            `}</style>

            {/* @ts-expect-error - math-field is a custom element */}
            <math-field
                ref={mfRef}
                math-virtual-keyboard-policy="auto"
                placeholder={placeholder}
                onInput={(evt: Event) => {
                    isInternalChange.current = true;
                    const nextValue = readMathFieldValue(evt.target as MathfieldElement | null);
                    onChange(nextValue);
                    isInternalChange.current = false;
                }}
                style={{
                    display: 'block',
                    width: '100%',
                    maxWidth: '100%',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    overflowWrap: 'anywhere',
                    overflowX: 'hidden',
                    color: mounted && isDark ? "white" : "inherit"
                }}
            >
                {value}
                {/* @ts-expect-error - math-field is a custom element */}
            </math-field>
        </div>
    );
});

MathInput.displayName = 'MathInput';

export default MathInput;
