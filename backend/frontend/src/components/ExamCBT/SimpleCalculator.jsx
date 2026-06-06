import React, { useEffect, useState } from "react";

const OPERATOR_LABELS = {
  add: "+",
  subtract: "-",
  multiply: "x",
  divide: "÷",
};

function calculate(left, right, operator) {
  const a = Number(left);
  const b = Number(right);

  if (!Number.isFinite(a) || !Number.isFinite(b)) return "Error";
  if (operator === "add") return String(a + b);
  if (operator === "subtract") return String(a - b);
  if (operator === "multiply") return String(a * b);
  if (operator === "divide") return b === 0 ? "Error" : String(a / b);
  return String(b);
}

const SimpleCalculator = () => {
  const [display, setDisplay] = useState("0");
  const [storedValue, setStoredValue] = useState(null);
  const [pendingOperator, setPendingOperator] = useState(null);
  const [waitingForNumber, setWaitingForNumber] = useState(false);

  const inputDigit = (digit) => {
    setDisplay((current) => {
      if (current === "Error" || waitingForNumber) {
        setWaitingForNumber(false);
        return digit;
      }
      return current === "0" ? digit : `${current}${digit}`;
    });
  };

  const inputDecimal = () => {
    setDisplay((current) => {
      if (current === "Error" || waitingForNumber) {
        setWaitingForNumber(false);
        return "0.";
      }
      return current.includes(".") ? current : `${current}.`;
    });
  };

  const clearAll = () => {
    setDisplay("0");
    setStoredValue(null);
    setPendingOperator(null);
    setWaitingForNumber(false);
  };

  const backspace = () => {
    setDisplay((current) => {
      if (current === "Error" || waitingForNumber || current.length <= 1) return "0";
      return current.slice(0, -1);
    });
  };

  const toggleSign = () => {
    setDisplay((current) => {
      if (current === "0" || current === "Error") return current;
      return current.startsWith("-") ? current.slice(1) : `-${current}`;
    });
  };

  const chooseOperator = (operator) => {
    if (display === "Error") {
      clearAll();
      return;
    }

    if (storedValue !== null && pendingOperator && !waitingForNumber) {
      const result = calculate(storedValue, display, pendingOperator);
      setDisplay(result);
      setStoredValue(result === "Error" ? null : result);
    } else {
      setStoredValue(display);
    }

    setPendingOperator(operator);
    setWaitingForNumber(true);
  };

  const showResult = () => {
    if (storedValue === null || !pendingOperator || waitingForNumber) return;
    const result = calculate(storedValue, display, pendingOperator);
    setDisplay(result);
    setStoredValue(null);
    setPendingOperator(null);
    setWaitingForNumber(true);
  };

  useEffect(() => {
    const handleKeyDown = (event) => {
      const target = event.target;
      const tagName = target?.tagName;
      const isTyping =
        tagName === "INPUT" ||
        tagName === "TEXTAREA" ||
        tagName === "SELECT" ||
        target?.isContentEditable;

      if (isTyping) return;

      const key = event.key;
      if (/^[0-9]$/.test(key)) {
        event.preventDefault();
        inputDigit(key);
        return;
      }
      if (key === ".") {
        event.preventDefault();
        inputDecimal();
        return;
      }
      if (key === "+" || key === "-" || key === "*" || key === "x" || key === "X" || key === "/") {
        event.preventDefault();
        const operatorMap = { "+": "add", "-": "subtract", "*": "multiply", x: "multiply", X: "multiply", "/": "divide" };
        chooseOperator(operatorMap[key]);
        return;
      }
      if (key === "Enter" || key === "=") {
        event.preventDefault();
        showResult();
        return;
      }
      if (key === "Backspace") {
        event.preventDefault();
        backspace();
        return;
      }
      if (key === "Delete" || key === "Escape" || key === "c" || key === "C") {
        event.preventDefault();
        clearAll();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [display, pendingOperator, storedValue, waitingForNumber]);

  return (
    <section className="simple-calculator" aria-label="Calculator">
      <div className="calculator-topline">
        <span>{pendingOperator ? `${storedValue} ${OPERATOR_LABELS[pendingOperator]}` : "Ready"}</span>
      </div>
      <output className="calculator-display" aria-live="polite">
        {display}
      </output>

      <div className="calculator-grid">
        <button type="button" className="calculator-key utility" onClick={clearAll}>
          C
        </button>
        <button type="button" className="calculator-key utility" onClick={backspace}>
          DEL
        </button>
        <button type="button" className="calculator-key utility" onClick={toggleSign}>
          +/-
        </button>
        <button type="button" className="calculator-key operator" onClick={() => chooseOperator("divide")}>
          ÷
        </button>

        {[7, 8, 9].map((digit) => (
          <button key={digit} type="button" className="calculator-key" onClick={() => inputDigit(String(digit))}>
            {digit}
          </button>
        ))}
        <button type="button" className="calculator-key operator" onClick={() => chooseOperator("multiply")}>
          x
        </button>

        {[4, 5, 6].map((digit) => (
          <button key={digit} type="button" className="calculator-key" onClick={() => inputDigit(String(digit))}>
            {digit}
          </button>
        ))}
        <button type="button" className="calculator-key operator" onClick={() => chooseOperator("subtract")}>
          -
        </button>

        {[1, 2, 3].map((digit) => (
          <button key={digit} type="button" className="calculator-key" onClick={() => inputDigit(String(digit))}>
            {digit}
          </button>
        ))}
        <button type="button" className="calculator-key operator" onClick={() => chooseOperator("add")}>
          +
        </button>

        <button type="button" className="calculator-key zero" onClick={() => inputDigit("0")}>
          0
        </button>
        <button type="button" className="calculator-key" onClick={inputDecimal}>
          .
        </button>
        <button type="button" className="calculator-key equals" onClick={showResult}>
          =
        </button>
      </div>
    </section>
  );
};

export default SimpleCalculator;
