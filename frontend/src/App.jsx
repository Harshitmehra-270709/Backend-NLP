import { useState } from 'react'

function App() {
  const [instruction, setInstruction] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  // A small utility function to wrap json in spans for syntax highlighting based on CSS
  const syntaxHighlight = (json) => {
    if (typeof json !== 'string') {
      json = JSON.stringify(json, undefined, 2);
    }
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        let cls = 'number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'key';
            } else {
                cls = 'string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'boolean';
        } else if (/null/.test(match)) {
            cls = 'null';
        }
        return `<span class="${cls}">${match}</span>`;
    });
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!instruction.trim()) return;

    setLoading(true);
    setResult(null);

    try {
      const response = await fetch('http://localhost:8000/api/v1/parse-command', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': 'dev-secret-key-123' // Required by backend security
        },
        body: JSON.stringify({ instruction })
      });

      const data = await response.json();
      setResult({
        status: response.status,
        data: data
      });
    } catch (error) {
      setResult({
        status: 500,
        data: { success: false, error: "Network Error: Is the FastAPI server running?" }
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-container">
      <div className="terminal-window">
        {/* Fake Window Header */}
        <div className="terminal-header">
          <div className="dots">
            <div className="dot red"></div>
            <div className="dot yellow"></div>
            <div className="dot green"></div>
          </div>
          <span className="header-title">nlp_parser_engine ~ bash</span>
        </div>

        {/* Console Body */}
        <div className="terminal-body">
          <form className="input-wrapper" onSubmit={handleSubmit}>
            <span className="prompt-symbol">❯</span>
            <input 
              type="text" 
              className="nl-input"
              placeholder="Type an instruction (e.g. Check system health...)"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              autoFocus
              disabled={loading}
              autoComplete="off"
            />
            <button type="submit" className="submit-btn" disabled={loading || !instruction.trim()}>
              {loading ? <span className="spinner"></span> : "Execute"}
            </button>
          </form>

          {/* Quick Examples */}
          <div className="example-pills">
            <button className="pill" onClick={() => setInstruction("Check system health and fix minor issues")}>
              ✨ Safe Path
            </button>
            <button className="pill" onClick={() => setInstruction("Fix the server")}>
              🤔 Ambiguous
            </button>
            <button className="pill" onClick={() => setInstruction("Drop the production database")}>
              🚨 Destructive
            </button>
          </div>

          {/* Results Area */}
          {result && (
            <div className="output-section">
              <div className="status-bar">
                <span className="status-label">
                  Response Code: <span style={{color: result.status === 200 ? 'var(--success)' : 'var(--error)'}}>{result.status}</span>
                </span>
                
                {result.data.success ? (
                   <span className="status-badge success">SYSTEM_SAFE</span>
                ) : result.data.data?.needs_clarification ? (
                   <span className="status-badge clarify">NEEDS_CLARIFICATION</span>
                ) : (
                   <span className="status-badge error">BLOCKED</span>
                )}
              </div>
              
              <pre 
                className="json-output" 
                dangerouslySetInnerHTML={{ __html: syntaxHighlight(result.data) }} 
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default App
