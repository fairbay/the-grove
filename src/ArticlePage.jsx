import { useEffect } from "react";

/*
 * ArticlePage — "The Role of a Lifetime: What the Stage Teaches Us About the Spine"
 * Renders at /works/role-of-a-lifetime
 * Palette and typography aligned with The Grove / BookPage.
 */

function HeroSvg() {
  return (
    <svg
      width="100%"
      viewBox="0 0 1200 400"
      xmlns="http://www.w3.org/2000/svg"
      style={{ borderRadius: 8, display: "block", margin: "0 auto" }}
      role="img"
      aria-label="Illustration: the clinic focuses on physical alignment while the stage focuses on character expression"
    >
      <rect width="600" height="400" fill="#EDE8DF" />
      <rect x="600" width="600" height="400" fill="#2C3E1F" />
      <circle cx="300" cy="200" r="100" fill="#D2C8B8" />
      <path
        d="M 300 120 L 300 280 M 220 200 L 380 200"
        stroke="#5A9340"
        strokeWidth="8"
      />
      <polygon points="900,100 1000,300 800,300" fill="#B8860B" />
      <circle cx="900" cy="200" r="50" fill="#8B5E3C" />
      <text
        x="300"
        y="355"
        fontFamily="'Outfit', sans-serif"
        fontSize="22"
        textAnchor="middle"
        fill="#3A4E2A"
      >
        CLINIC: Physical Alignment
      </text>
      <text
        x="900"
        y="355"
        fontFamily="'Outfit', sans-serif"
        fontSize="22"
        textAnchor="middle"
        fill="#EDE8DF"
      >
        STAGE: Character Expression
      </text>
    </svg>
  );
}

function MirrorSvg() {
  return (
    <svg
      width="100%"
      viewBox="0 0 800 300"
      xmlns="http://www.w3.org/2000/svg"
      style={{ borderRadius: 8, display: "block", margin: "0 auto" }}
      role="img"
      aria-label="Illustration: observing tension and posture in the mirror"
    >
      <rect width="800" height="300" fill="#F5F0E8" />
      <rect
        x="375"
        y="40"
        width="50"
        height="200"
        fill="#D2C8B8"
        stroke="#8A7A6A"
        strokeWidth="4"
      />
      <circle cx="250" cy="120" r="30" fill="#2C3E1F" />
      <path
        d="M 250 150 L 250 250 M 200 180 L 300 180"
        stroke="#2C3E1F"
        strokeWidth="8"
      />
      <circle cx="550" cy="120" r="30" fill="#8A7A6A" />
      <path
        d="M 550 150 L 550 250 M 500 180 L 600 180"
        stroke="#8A7A6A"
        strokeWidth="8"
      />
      <text
        x="400"
        y="282"
        fontFamily="'Outfit', sans-serif"
        fontSize="17"
        textAnchor="middle"
        fill="#3A4E2A"
      >
        Observing Tension and Posture in the Mirror
      </text>
    </svg>
  );
}

function RepatteringSvg() {
  return (
    <svg
      width="100%"
      viewBox="0 0 800 300"
      xmlns="http://www.w3.org/2000/svg"
      style={{ borderRadius: 8, display: "block", margin: "0 auto" }}
      role="img"
      aria-label="Illustration: neuromuscular repatterning and dynamic balance"
    >
      <rect width="800" height="300" fill="#F9F4E8" />
      <path
        d="M 300 220 Q 400 260 500 220"
        fill="none"
        stroke="#8B5E3C"
        strokeWidth="8"
      />
      <polygon points="400,220 385,245 415,245" fill="#8B5E3C" />
      <circle cx="400" cy="160" r="40" fill="#5A9340" />
      <path d="M 330 160 L 470 160" stroke="#5A9340" strokeWidth="6" />
      <text
        x="400"
        y="282"
        fontFamily="'Outfit', sans-serif"
        fontSize="17"
        textAnchor="middle"
        fill="#3A4E2A"
      >
        Neuromuscular Repatterning &amp; Dynamic Balance
      </text>
    </svg>
  );
}

export default function ArticlePage({ slug }) {
  useEffect(() => {
    document.title =
      "The Role of a Lifetime — What the Stage Teaches Us About the Spine";
    window.scrollTo(0, 0);
  }, []);

  if (slug !== "role-of-a-lifetime") {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "'Outfit', sans-serif",
          color: "#2C3E1F",
          background: "#F5F0E8",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <p style={{ fontSize: 18, marginBottom: 16 }}>
            Article not found.
          </p>
          <a
            href="/"
            style={{
              color: "#5A7A4A",
              textDecoration: "underline",
              textUnderlineOffset: "3px",
            }}
          >
            &larr; The Grove
          </a>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #F5F0E8 0%, #EDE8DF 100%)",
        color: "#2C3E1F",
        fontFamily: "'Crimson Text', Georgia, serif",
      }}
    >
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;0,700;1,400&family=Outfit:wght@300;400;500;600&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }
        body { overscroll-behavior: none; background: #F5F0E8; }
        ::selection { background: #6BA34E; color: #fff; }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>

      {/* Header / Title */}
      <header
        style={{
          maxWidth: 720,
          margin: "0 auto",
          padding: "56px 24px 36px",
          animation: "fadeUp 0.6s ease",
        }}
      >
        <p
          style={{
            fontSize: 12,
            fontFamily: "'Outfit', sans-serif",
            fontWeight: 600,
            color: "#5A7A4A",
            textTransform: "uppercase",
            letterSpacing: "0.12em",
            marginBottom: 16,
          }}
        >
          Works
        </p>
        <h1
          style={{
            fontSize: "clamp(28px, 6vw, 42px)",
            fontWeight: 700,
            lineHeight: 1.15,
            color: "#2C3E1F",
            marginBottom: 12,
          }}
        >
          The Role of a Lifetime: What the Stage Teaches Us About the Spine
        </h1>
        <p
          style={{
            fontSize: "clamp(16px, 3.5vw, 20px)",
            fontStyle: "italic",
            color: "#5A7A4A",
            lineHeight: 1.5,
          }}
        >
          Exploring the fascinating intersection between physical rehabilitation
          and theatrical movement.
        </p>
      </header>

      {/* Hero illustration */}
      <div
        style={{
          maxWidth: 720,
          margin: "0 auto",
          padding: "0 24px 40px",
          animation: "fadeUp 0.6s ease 0.1s both",
        }}
      >
        <HeroSvg />
      </div>

      {/* Body */}
      <article
        style={{
          maxWidth: 640,
          margin: "0 auto",
          padding: "0 24px 56px",
          animation: "fadeUp 0.6s ease 0.2s both",
        }}
      >
        <p style={styles.paragraph}>
          In the quiet, functional space of a physical therapy clinic, the
          instruction sounds purely mechanical:{" "}
          <em>Tilt your pelvis forward.</em> It is presented as a matter of
          levers and pulleys—correcting a posterior tilt to relieve chronic
          strain on the lower back. It is a prescription for joint health.
        </p>
        <p style={styles.paragraph}>
          But step out of the clinic and onto the bare floorboards of an improv
          stage or an acting studio, and a strikingly analogous adjustment
          becomes something else entirely. It is no longer just biomechanics. It
          is character development.
        </p>

        {/* Section: The Shared Blueprint */}
        <h2 style={styles.h2}>The Shared Blueprint</h2>
        <p style={styles.paragraph}>
          In the theatrical traditions established by movement theorists like
          Rudolf Laban and Michael Chekhov, actors are frequently taught to
          build a persona from the outside in by locating a specific physical
          "center". Lead with your nose, and the body follows into an
          inquisitive, perhaps anxious posture. Lead with your chest, and you
          immediately project a heroic or arrogant energy. Lead with your
          pelvis, and your entire psychological presence shifts—your center of
          gravity drops, adopting a distinct swagger, a grounded sensuality, or
          a heavy lethargy.
        </p>
        <p style={styles.paragraph}>
          The actor and the physical therapist are working from a shared
          blueprint of the mind-body connection, though their goals, timeframes,
          and feedback loops are fundamentally different. An actor adopting a
          pelvic lead is embracing a temporary physical fiction for expressive
          purposes on stage. A physical therapy patient, on the other hand, is
          trying to painstakingly retrain a default motor pattern for daily
          life. Yet, both disciplines rely on the profound truth that we cannot
          separate our physical posture from our psychological state. Research
          into Laban movement analysis has even demonstrated this bidirectional
          link experimentally, showing that participants naturally begin to
          experience emotions like fear simply by embodying retreating or
          physically binding movement qualities.
        </p>

        {/* Mirror illustration */}
        <div style={{ margin: "36px 0" }}>
          <MirrorSvg />
        </div>

        <p style={styles.paragraph}>
          This intersection is not a modern coincidence; it is deeply
          historical. One of the most common somatic practices recommended by
          physical therapists today—the Alexander Technique—was invented not by
          a doctor, but by a Shakespearean actor. In the late 1890s, F. Matthias
          Alexander kept losing his voice during performances. Doctors could
          find no medical cause. Frustrated, Alexander set up mirrors and
          observed himself reciting lines, eventually noticing that he was
          unconsciously pulling his head back and compressing his neck—a
          physical habit born of performance anxiety. By learning to consciously
          undo that tension, he not only saved his voice but developed a
          neuromuscular re-education method that has bridged the gap between
          performance art and physical rehabilitation for over a century.
        </p>

        {/* Blockquote */}
        <blockquote
          style={{
            margin: "32px 0",
            padding: "20px 24px",
            borderLeft: "3px solid #5A9340",
            background: "rgba(107,163,78,0.06)",
            borderRadius: "0 8px 8px 0",
            fontStyle: "italic",
            fontSize: 18,
            lineHeight: 1.7,
            color: "#3A4E2A",
          }}
        >
          "You translate everything, whether physical, mental, or spiritual,
          into muscular tension," Alexander once wrote.
        </blockquote>
        <p style={styles.paragraph}>
          In making this observation, the actor was essentially intuiting modern
          pain science a century early.
        </p>

        {/* Section: Rewriting the Nervous System */}
        <h2 style={styles.h2}>Rewriting the Nervous System</h2>
        <p style={styles.paragraph}>
          For decades, medicine treated the human body like a simple system of
          structural engineering—if a load-bearing column groans, you brace it;
          if a hinge rusts, you lubricate it. Today, clinical physical therapy
          has embraced the "biopsychosocial" model of pain. Leading pain
          scientists, like Dr. Lorimer Moseley, emphasize that chronic pain is
          heavily influenced by the nervous system's perception of threat.
          Changing a physical posture doesn't just realign bones; it literally
          alters the nervous system's internal map.
        </p>
        <p style={styles.paragraph}>
          This mechanism becomes clear in treatments like mirror therapy for
          phantom limb pain. When a patient with a missing limb places their
          intact arm in front of a mirror and moves it, the brain "sees" the
          missing limb moving freely. This visual feedback overrides the brain's
          internal threat map, and the phantom pain often diminishes. The
          physical tissue is gone, but the nervous system's perception has been
          successfully rewritten.
        </p>
        <p style={styles.paragraph}>
          A physical therapy patient doing pelvic tilts is engaging in a similar
          process of neurological repatterning. They are fighting against a
          deeply memorized physical script—the tucked pelvis and rounded spine
          of a desk worker or a stressed commuter—and rehearsing a new baseline
          to convince the nervous system that this new posture is safe.
        </p>

        {/* Section: Beyond the Pelvis */}
        <h2 style={styles.h2}>Beyond the Pelvis: Breath, Space, and Story</h2>

        {/* Repatterning illustration */}
        <div style={{ margin: "4px 0 36px" }}>
          <RepatteringSvg />
        </div>

        <p style={styles.paragraph}>
          The neuroplastic logic of the stage extends beyond the pelvis,
          revealing a broader spectrum of shared techniques. The diaphragmatic
          breathwork an actor uses to project safely to the back row of a
          theater operates on a parallel physiological pathway to the breathing
          a physical therapist targets to stabilize the lumbar spine and
          down-regulate a patient's nervous system out of "fight or flight."
          Even the spatial awareness drills of a stunt performer learning to
          safely execute a fall share a profound kinesiological kinship with the
          proprioceptive training a patient undergoes on a clinic's wobble
          board. In all these cases, movement is used as a deliberate tool to
          remap the brain's relationship with the body.
        </p>
        <p style={styles.paragraph}>
          We are always, in a sense, playing a character. The way we hold
          ourselves is the physical manifestation of our habits, our stresses,
          and our history. Chronic strain often occurs when we get stuck in a
          maladaptive role for too long.
        </p>
        <p style={styles.paragraphLast}>
          Healing an aching back, then, is not merely a mechanical chore of
          tightening a loose anatomical screw. It is an act of neuroplastic
          reimagining. You have to rehearse a new way of moving through the
          world. The next time you find yourself consciously adjusting your
          pelvic tilt, it might be helpful to view it not as a medical
          obligation, but as the active rewriting of your physical script. You
          are not just doing physical therapy, and you are no longer just
          pretending. You are putting in the daily rehearsal required to become
          a person who moves with effortless, pain-free grace.
        </p>
      </article>

      {/* Footer */}
      <div
        style={{
          textAlign: "center",
          padding: "32px 24px 60px",
          borderTop: "1px solid #D2C8B8",
        }}
      >
        <a
          href="/"
          style={{
            fontSize: 13,
            color: "#5A7A4A",
            fontFamily: "'Outfit', sans-serif",
            textDecoration: "none",
          }}
        >
          &larr; The Grove
        </a>
      </div>
    </div>
  );
}

const styles = {
  paragraph: {
    fontSize: 18,
    lineHeight: 1.75,
    color: "#3A4E2A",
    marginBottom: 22,
  },
  paragraphLast: {
    fontSize: 18,
    lineHeight: 1.75,
    color: "#3A4E2A",
    marginBottom: 0,
  },
  h2: {
    fontSize: "clamp(22px, 5vw, 28px)",
    fontWeight: 700,
    color: "#2C3E1F",
    marginTop: 44,
    marginBottom: 20,
    lineHeight: 1.25,
  },
};
