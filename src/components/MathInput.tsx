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
                    white-space: pre-wrap !important; /* Force wrap */
                    word-break: break-word !important;
                    overflow-wrap: anywhere !important;
                    text-align: left;
                }
            `}</style>
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
