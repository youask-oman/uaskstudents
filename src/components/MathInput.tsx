"use client";

import React, { useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import { CUSTOM_KEYBOARD_LAYOUT } from '@/lib/math-layout';
import 'mathlive/static.css';

interface MathInputProps {
    value: string;
    onChange: (latex: string) => void;
    placeholder?: string;
    onEnter?: () => void;
    className?: string;
}

export interface MathInputRef {
    insert: (latex: string) => void;
    focus: () => void;
    setValue: (latex: string) => void;
}

const MathInput = forwardRef<MathInputRef, MathInputProps>(({ value, onChange, placeholder, onEnter, className = "" }, ref) => {
    const mfRef = useRef<HTMLElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const isInternalChange = useRef(false);

    // Background Color Customization
    const [kbBg, setKbBg] = React.useState('#ffffff');
    const COLORS = [
        { name: 'Light', value: 'rgba(255, 255, 255, 0.95)', border: '#e2e8f0' },
        { name: 'Dark', value: '#1e293b', border: '#334155' },
        { name: 'Blue', value: '#3b82f6', border: '#2563eb' },
        { name: 'Green', value: '#10b981', border: '#059669' },
        { name: 'Purple', value: '#8b5cf6', border: '#7c3aed' },
        { name: 'Rose', value: '#f43f5e', border: '#e11d48' }
    ];

    useEffect(() => {
        // Dynamically import mathlive to avoid SSR issues
        import('mathlive').then((m) => {
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

    useImperativeHandle(ref, () => ({
        insert: (latex: string) => {
            if (mfRef.current) {
                (mfRef.current as any).executeCommand(['insert', latex]);
                (mfRef.current as any).focus();
            }
        },
        focus: () => {
            if (mfRef.current) {
                (mfRef.current as any).focus();
            }
        },
        setValue: (latex: string) => {
            if (mfRef.current) {
                (mfRef.current as any).setValue(latex);
            }
        }
    }));

    useEffect(() => {
        const mf = mfRef.current;
        if (!mf) return;

        const handleInput = (e: Event) => {
            isInternalChange.current = true;
            onChange((e.target as any).value);
            isInternalChange.current = false;
        };

        // Keydown handler for Enter
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                onEnter?.();
            }
        };

        mf.addEventListener('input', handleInput);
        mf.addEventListener('keydown', handleKeyDown as any);

        return () => {
            mf.removeEventListener('input', handleInput);
            mf.removeEventListener('keydown', handleKeyDown as any);
        };
    }, [onChange, onEnter]);

    // Sync external value changes
    useEffect(() => {
        if (mfRef.current && (mfRef.current as any).value !== value && !isInternalChange.current) {
            (mfRef.current as any).value = value;
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

            {/* Theme Picker Row */}
            <div className="flex items-center gap-3 mb-2 px-2 py-1 bg-slate-100/50 dark:bg-slate-800/50 rounded-lg border border-slate-200 dark:border-slate-700 w-fit">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest pl-1">Theme</span>
                <div className="flex gap-2">
                    {COLORS.map(color => (
                        <button
                            key={color.name}
                            onClick={() => setKbBg(color.value)}
                            className={`w-4 h-4 rounded-full border-2 transition-transform hover:scale-125 ${kbBg === color.value ? 'ring-2 ring-primary ring-offset-1 ring-offset-white dark:ring-offset-slate-900 border-white' : 'border-transparent'}`}
                            style={{ backgroundColor: color.value, borderColor: color.value === 'rgba(255, 255, 255, 0.95)' ? '#e2e8f0' : color.value }}
                            title={color.name}
                        />
                    ))}
                </div>
            </div>

            {/* @ts-ignore - math-field is a custom element */}
            <math-field
                ref={mfRef}
                math-virtual-keyboard-policy="auto"
                placeholder={placeholder}
                onInput={(evt: Event) => {
                    isInternalChange.current = true;
                    onChange((evt.target as any).value);
                    isInternalChange.current = false;
                }}
                style={{
                    display: 'block',
                    width: '100%',
                    maxWidth: '100%',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    overflowWrap: 'anywhere',
                    overflowX: 'hidden'
                }}
            >
                {value}
            </math-field>
        </div>
    );
});

MathInput.displayName = 'MathInput';

export default MathInput;
