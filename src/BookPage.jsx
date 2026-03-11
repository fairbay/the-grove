import { useState, useEffect } from "react";

/*
 * BookPage — Landing page for Stage Directions ebook.
 * Renders at /books/stage-directions
 * Color scheme aligned with The Grove's nature palette.
 */

const CHAPTERS = [
  { title: "Stage Fright", teaser: "Why 'calm down' is the worst advice" },
  { title: "The Fourth Wall", teaser: "The skill of seeing your own patterns" },
  { title: "Understudies", teaser: "Why your life needs redundancy" },
  { title: "Blocking", teaser: "How your environment runs your behavior" },
  { title: "The Green Room", teaser: "The case for non-productive time" },
  { title: "Notes from the Director", teaser: "Hearing feedback without making it personal" },
  { title: "Costume Design", teaser: "You're already managing impressions" },
  { title: "Dark Theater", teaser: "When there's no show running" },
  { title: "The Ensemble", teaser: "Why great teams listen, not just perform" },
  { title: "Rehearsal vs. Performance", teaser: "The gap between practice and the real thing" },
  { title: "Breaking Character", teaser: "When the role no longer fits" },
  { title: "The Prompt Book", teaser: "Systems that free your mind" },
  { title: "Curtain Call", teaser: "The art of ending well" },
  { title: "Improv", teaser: "Yes, And" },
];

export default function BookPage() {
  const [hoveredCh, setHoveredCh] = useState(null);

  useEffect(() => {
    document.title = "Stage Directions — Wisdom from the World's Players";
  }, []);

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(180deg, #F5F0E8 0%, #EDE8DF 100%)",
      color: "#2C3E1F",
      fontFamily: "'Crimson Text', Georgia, serif",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;0,700;1,400&family=Outfit:wght@300;400;500;600&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }
        body { overscroll-behavior: none; background: #F5F0E8; }
        ::selection { background: #6BA34E; color: #fff; }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>

      {/* Hero */}
      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        padding: "60px 24px 48px",
        maxWidth: 800,
        margin: "0 auto",
        animation: "fadeUp 0.6s ease",
      }}>
        {/* Cover */}
        <div style={{
          width: "min(280px, 60vw)",
          borderRadius: 4,
          overflow: "hidden",
          boxShadow: "0 20px 60px rgba(0,0,0,0.15), 0 0 80px rgba(107,163,78,0.1)",
          marginBottom: 36,
        }}>
          <img
            src="/stage-directions-cover.png"
            alt="Stage Directions book cover"
            style={{ width: "100%", display: "block" }}
          />
        </div>

        {/* Title */}
        <h1 style={{
          fontSize: "clamp(32px, 7vw, 48px)",
          fontWeight: 700,
          textAlign: "center",
          lineHeight: 1.1,
          marginBottom: 8,
          color: "#2C3E1F",
        }}>
          Stage Directions
        </h1>
        <p style={{
          fontSize: "clamp(16px, 3.5vw, 22px)",
          fontStyle: "italic",
          color: "#5A7A4A",
          textAlign: "center",
          marginBottom: 16,
        }}>
          Wisdom from the World's Players
        </p>
        <p style={{
          fontSize: 14,
          color: "#8A7A6A",
          textAlign: "center",
          marginBottom: 32,
          fontFamily: "'Outfit', sans-serif",
          letterSpacing: "0.03em",
        }}>
          Written by Claude · Directed by Baylee Miller
        </p>

        {/* CTA */}
        <a
          href="/Stage-Directions.epub"
          download="Stage-Directions.epub"
          style={{
            display: "inline-block",
            padding: "14px 40px",
            borderRadius: 8,
            background: "#5A9340",
            color: "#fff",
            fontSize: 16,
            fontWeight: 600,
            fontFamily: "'Outfit', sans-serif",
            textDecoration: "none",
            letterSpacing: "0.02em",
            boxShadow: "0 4px 20px rgba(90,147,64,0.3)",
            transition: "transform 0.15s ease, box-shadow 0.15s ease",
          }}
          onMouseOver={e => { e.target.style.transform = "translateY(-2px)"; e.target.style.boxShadow = "0 6px 28px rgba(90,147,64,0.4)"; }}
          onMouseOut={e => { e.target.style.transform = ""; e.target.style.boxShadow = "0 4px 20px rgba(90,147,64,0.3)"; }}
        >
          Download free
        </a>
        <p style={{ fontSize: 12, color: "#8A7A6A", marginTop: 10, fontFamily: "'Outfit', sans-serif" }}>
          epub · opens in Apple Books, Google Play Books, or any ebook reader
        </p>
        <a
          href="https://bayleemill.gumroad.com/l/stage-directions"
          target="_blank"
          rel="noopener noreferrer"
          style={{ fontSize: 13, color: "#8A7A6A", fontFamily: "'Outfit', sans-serif", textDecoration: "none", marginTop: 12, display: "inline-block" }}
        >
          {"Enjoyed it? Support this project on Gumroad \u2192"}
        </a>
      </div>

      {/* Divider */}
      <div style={{ width: 40, height: 1, background: "#D2C8B8", margin: "0 auto 48px" }} />

      {/* Pitch */}
      <div style={{
        maxWidth: 600,
        margin: "0 auto",
        padding: "0 24px 48px",
        animation: "fadeUp 0.6s ease 0.15s both",
      }}>
        <p style={{ fontSize: 18, lineHeight: 1.7, color: "#3A4E2A", marginBottom: 20 }}>
          For thousands of years, theatre has been humanity's laboratory for the problems of being alive.
          How do I show up when I'm terrified? How do I hear criticism without falling apart?
          When do I follow the script, and when do I throw it away?
        </p>
        <p style={{ fontSize: 18, lineHeight: 1.7, color: "#3A4E2A", marginBottom: 20 }}>
          This book takes fourteen concepts from theatre and maps each one to a practical life skill,
          drawing on the work of researchers and writers like Brené Brown, Oliver Burkeman, Angela Duckworth,
          Tina Fey, Erving Goffman, and two dozen others.
        </p>
        <p style={{ fontSize: 16, lineHeight: 1.7, color: "#5C6A4A" }}>
          <strong style={{ color: "#2C3E1F" }}>This book was written by Claude, an AI made by Anthropic.</strong>{" "}
          That's stated on page one, because a book about honesty shouldn't start with a secret.
          The ideas belong to the human experts cited in every chapter.
        </p>
      </div>

      {/* Stats bar */}
      <div style={{
        display: "flex",
        justifyContent: "center",
        gap: "clamp(24px, 6vw, 56px)",
        padding: "24px",
        borderTop: "1px solid #D2C8B8",
        borderBottom: "1px solid #D2C8B8",
        marginBottom: 48,
        background: "rgba(107,163,78,0.06)",
        animation: "fadeUp 0.6s ease 0.3s both",
      }}>
        {[
          { number: "14", label: "theatre concepts" },
          { number: "30+", label: "expert voices" },
          { number: "~1 hr", label: "reading time" },
        ].map(s => (
          <div key={s.label} style={{ textAlign: "center" }}>
            <div style={{ fontSize: 28, fontWeight: 700, color: "#2C3E1F" }}>{s.number}</div>
            <div style={{ fontSize: 11, color: "#5A7A4A", fontFamily: "'Outfit', sans-serif", textTransform: "uppercase", letterSpacing: "0.1em", marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Chapter list */}
      <div style={{
        maxWidth: 600,
        margin: "0 auto",
        padding: "0 24px 56px",
        animation: "fadeUp 0.6s ease 0.4s both",
      }}>
        <h2 style={{
          fontSize: 13,
          fontFamily: "'Outfit', sans-serif",
          fontWeight: 600,
          color: "#5A7A4A",
          textTransform: "uppercase",
          letterSpacing: "0.12em",
          marginBottom: 20,
        }}>
          Inside
        </h2>
        {CHAPTERS.map((ch, i) => (
          <div
            key={i}
            onMouseOver={() => setHoveredCh(i)}
            onMouseOut={() => setHoveredCh(null)}
            style={{
              padding: "12px 0",
              borderBottom: "1px solid #DDD8D0",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              gap: 16,
              transition: "padding-left 0.15s ease",
              paddingLeft: hoveredCh === i ? 8 : 0,
            }}
          >
            <span style={{
              fontSize: 17,
              fontWeight: 600,
              color: hoveredCh === i ? "#2C3E1F" : "#3A4E2A",
              transition: "color 0.15s",
            }}>
              {ch.title}
            </span>
            <span style={{
              fontSize: 14,
              fontStyle: "italic",
              color: "#8A7A6A",
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}>
              {ch.teaser}
            </span>
          </div>
        ))}
      </div>

      {/* Bottom CTA */}
      <div style={{
        textAlign: "center",
        padding: "32px 24px 60px",
        borderTop: "1px solid #D2C8B8",
      }}>
        <a
          href="/Stage-Directions.epub"
          download="Stage-Directions.epub"
          style={{
            display: "inline-block",
            padding: "14px 40px",
            borderRadius: 8,
            background: "#5A9340",
            color: "#fff",
            fontSize: 16,
            fontWeight: 600,
            fontFamily: "'Outfit', sans-serif",
            textDecoration: "none",
            letterSpacing: "0.02em",
            boxShadow: "0 4px 20px rgba(90,147,64,0.3)",
          }}
        >
          Download free
        </a>

        <div style={{ marginTop: 20 }}>
          <a
            href="https://bayleemill.gumroad.com/l/stage-directions"
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 13, color: "#8A7A6A", fontFamily: "'Outfit', sans-serif", textDecoration: "none" }}
          >
            {"Enjoyed it? Support this project on Gumroad \u2192"}
          </a>
        </div>

        <div style={{ marginTop: 24 }}>
          <a href="/" style={{ fontSize: 13, color: "#5A7A4A", fontFamily: "'Outfit', sans-serif", textDecoration: "none" }}>
            {"\u2190 The Grove"}
          </a>
        </div>
      </div>
    </div>
  );
}