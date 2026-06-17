import { useEffect, useRef } from "react";

/*
 * ArticlePage — "The Role of a Lifetime"
 * Renders at /works/role-of-a-lifetime
 *
 * Design: cool teal palette (clinical + theatrical), stage-lighting
 * crossfade transitions between sections, act/scene structure.
 * Typography: Cormorant (display) + Source Serif 4 (body) + DM Sans (utility).
 */

function Reveal({ children, className = "", delay = 0 }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add("visible");
          obs.unobserve(el);
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const delayClass = delay > 0 ? ` reveal-delay-${delay}` : "";
  return (
    <div ref={ref} className={`reveal${delayClass} ${className}`}>
      {children}
    </div>
  );
}

export default function ArticlePage({ slug }) {
  useEffect(() => {
    document.title =
      "The Role of a Lifetime \u2014 What the Stage Teaches Us About the Spine";
    window.scrollTo(0, 0);
  }, []);

  if (slug !== "role-of-a-lifetime") {
    return (
      <div className="notfound-wrap">
        <style>{STYLES}</style>
        <p style={{ fontSize: 18, marginBottom: 16, color: "#E8EDE9" }}>
          Article not found.
        </p>
        <a
          href="/"
          style={{
            color: "#B08D57",
            textDecoration: "underline",
            textUnderlineOffset: "3px",
          }}
        >
          &larr; The Grove
        </a>
      </div>
    );
  }

  return (
    <div className="article-root">
      <style>{STYLES}</style>

      {/* HERO */}
      <section className="hero">
        <Reveal>
          <p className="utility hero-overline">Essay</p>
        </Reveal>
        <Reveal delay={1}>
          <h1 className="display hero-title">
            The Role of
            <br />a <em>Lifetime</em>
          </h1>
        </Reveal>
        <Reveal delay={2}>
          <p className="body-text hero-subtitle">
            What the stage teaches us about the spine.
          </p>
        </Reveal>
      </section>

      {/* LEDE */}
      <section className="lede-section">
        <Reveal>
          <p className="body-text lede-text">
            <em>Tilt your pelvis forward.</em>
          </p>
          <p className="body-text lede-text">
            In the clinic, that instruction is mechanical—levers and pulleys, a
            posterior tilt corrected to relieve lower-back strain. It is a
            prescription for joint health.
          </p>
          <p className="body-text lede-text">
            Now step onto the bare floorboards of a stage. The same adjustment
            becomes something else entirely:{" "}
            <strong>character development.</strong>
          </p>
        </Reveal>
      </section>

      <div className="crossfade-to-light" />

      {/* I. THE SHARED BLUEPRINT */}
      <section className="section-light">
        <Reveal>
          <p className="utility act-number">I</p>
        </Reveal>
        <Reveal delay={1}>
          <h2 className="display section-title">The Shared Blueprint</h2>
        </Reveal>

        <Reveal>
          <p className="body-text prose">
            Movement theorists like Rudolf Laban and Michael Chekhov taught
            actors to construct a persona from the outside in—to locate a
            physical center and let the psyche follow. Lead with your nose and
            the body folds into something inquisitive, maybe anxious. Lead with
            your chest and you project heroism or arrogance. Lead with your
            pelvis and your center of gravity drops: swagger, sensuality,
            lethargy.
          </p>
          <p className="body-text prose">
            The actor and the physical therapist are reading the same anatomical
            blueprint. Their goals are different—an actor adopts a pelvic lead
            for a two-hour fiction; a patient is trying to retrain a motor
            pattern they'll carry for decades. But both disciplines rest on a
            truth neither invented: you cannot separate physical posture from
            psychological state.
          </p>
          <p className="body-text prose">
            Laban movement research has demonstrated this bidirectional link
            experimentally. Participants who were asked to embody retreating,
            physically constricting movement qualities didn't just look
            afraid—they began to <em>feel</em> it. The body was not illustrating
            the mind. It was <em>instructing</em> it.
          </p>
        </Reveal>

        <div className="scene-mark">
          <span className="scene-mark-dot" />
        </div>

        <Reveal>
          <p className="body-text prose">
            This intersection is not a modern discovery. One of the most common
            somatic practices in physical therapy today—the Alexander
            Technique—was invented not by a doctor, but by a Shakespearean
            actor.
          </p>
          <p className="body-text prose">
            In the late 1890s, F. Matthias Alexander kept losing his voice
            mid-performance. Doctors found nothing wrong. Frustrated, Alexander
            set up a pair of mirrors and began reciting his lines while watching
            himself. What he saw surprised him: at the moment of greatest vocal
            effort, he was unconsciously wrenching his head backward and
            compressing his neck. A physical habit—born of performance
            anxiety—was strangling the voice it was trying to produce.
          </p>
          <p className="body-text prose">
            He spent years learning to consciously undo that tension. In the
            process, he developed a neuromuscular re-education method that has
            bridged performance art and physical rehabilitation for over a
            century.
          </p>
        </Reveal>

        <Reveal>
          <div className="pull-quote">
            <p className="display pull-quote-text">
              You translate everything—whether physical, mental, or
              spiritual—into muscular tension.
            </p>
            <p className="utility pull-quote-attr">F. Matthias Alexander</p>
          </div>
        </Reveal>

        <Reveal>
          <p className="body-text prose">
            In writing that sentence, the actor intuited modern pain science a
            hundred years early.
          </p>
        </Reveal>
      </section>

      <div className="crossfade-to-dark" />

      {/* II. REWRITING THE NERVOUS SYSTEM */}
      <section className="section-dark">
        <Reveal>
          <p className="utility act-number">II</p>
        </Reveal>
        <Reveal delay={1}>
          <h2 className="display section-title">
            Rewriting the Nervous System
          </h2>
        </Reveal>

        <Reveal>
          <p className="body-text prose">
            For decades, medicine modeled the human body as structural
            engineering. A groaning column gets braced. A rusted hinge gets
            lubricated. The body was a building and the therapist was a
            contractor.
          </p>
          <p className="body-text prose">
            That model has collapsed. Clinical physical therapy now works from
            what's called the <em>biopsychosocial</em> model of pain—an
            acknowledgment that chronic pain is not just tissue damage but
            nervous-system perception. Leading pain scientists like Dr. Lorimer
            Moseley emphasize that the brain maintains an internal threat map,
            and that changing posture doesn't merely shift bones. It rewrites
            the map itself.
          </p>
        </Reveal>

        <div className="scene-mark">
          <span className="scene-mark-dot" />
        </div>

        <Reveal>
          <p className="body-text prose">
            The most vivid proof of this is mirror therapy for phantom limb
            pain. A patient with a missing arm places their intact arm in front
            of a mirror. When they move it, the brain <em>sees</em> the missing
            limb moving freely. The visual feedback overrides the threat map.
            The phantom pain—pain in tissue that no longer exists—often
            diminishes.
          </p>
          <p className="body-text prose">
            The physical tissue is gone. But the nervous system's story about it
            has been successfully edited.
          </p>
        </Reveal>

        <Reveal>
          <div className="pull-quote">
            <p className="display pull-quote-text">
              A patient doing pelvic tilts is rehearsing a new baseline—fighting
              a deeply memorized script and trying to convince the nervous system
              that this new posture is safe.
            </p>
          </div>
        </Reveal>

        <Reveal>
          <p className="body-text prose">
            That tucked pelvis, that rounded spine—they are not structural
            failures. They are the posture of a desk worker. A stressed
            commuter. A person who has been playing the same physical role for so
            long that the nervous system treats it as permanent.
          </p>
        </Reveal>
      </section>

      <div className="crossfade-to-light" />

      {/* III. BREATH, SPACE, AND STORY */}
      <section className="section-light">
        <Reveal>
          <p className="utility act-number">III</p>
        </Reveal>
        <Reveal delay={1}>
          <h2 className="display section-title">Breath, Space, and Story</h2>
        </Reveal>

        <Reveal>
          <p className="body-text prose">
            The neuroplastic logic of the stage extends well beyond the pelvis.
            The diaphragmatic breathing an actor uses to project to the back row
            of a theater runs on the same physiological pathway a physical
            therapist targets to stabilize the lumbar spine and coax a patient's
            nervous system out of fight-or-flight. The spatial awareness drills
            of a stunt performer learning to fall safely share a deep
            kinesiological kinship with the proprioceptive training a patient
            does on a clinic's wobble board.
          </p>
          <p className="body-text prose">
            In every case the mechanism is the same: movement, used as a
            deliberate tool, remaps the brain's relationship with the body.
          </p>
        </Reveal>

        <div className="scene-mark">
          <span className="scene-mark-dot" />
        </div>

        <Reveal>
          <p className="body-text prose">
            We are always, in a sense, playing a character. The way we hold
            ourselves is the physical script of our habits, our stresses, our
            history. Chronic strain is what happens when we get stuck in a
            single role for too long—when the body forgets it has other options.
          </p>
        </Reveal>
      </section>

      <div className="crossfade-to-dark" />

      {/* CODA */}
      <section className="coda">
        <Reveal>
          <p className="display coda-text">
            Healing an aching back is not a mechanical repair. It is an act of
            neuroplastic reimagining—a rehearsal for a person who doesn't exist
            yet.
          </p>
          <p className="display coda-text">
            The next time you catch yourself adjusting your posture, try seeing
            it differently. Not as a medical obligation, but as a{" "}
            <em>rewrite.</em>
          </p>
          <p className="display coda-text">
            You are putting in the daily rehearsal required to become a person
            who moves with effortless, pain-free grace. That is the role of a
            lifetime.
          </p>
        </Reveal>
      </section>

      {/* FOOTER */}
      <footer className="article-footer">
        <p className="utility footer-byline">Baylee Miller &middot; 2026</p>
        <a href="/" className="utility footer-back">
          &larr; The Grove
        </a>
      </footer>
    </div>
  );
}

const STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=Cormorant:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400;1,500&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;0,8..60,500;0,8..60,600;1,8..60,300;1,8..60,400;1,8..60,500&family=DM+Sans:wght@300;400;500;600&display=swap');

  .article-root {
    --wing:       #1B2B30;
    --gauze:      #E8EDE9;
    --spotlight:   #B08D57;
    --gel:        #344B53;
    --smoke:      #8A9590;
    --warm-patch: #D4C9AD;
    --text-dark:  #2D2A26;
    --text-light: #D8D3CA;
  }
  .article-root, .article-root * { box-sizing: border-box; margin: 0; padding: 0; }
  .article-root { background: var(--wing); color: var(--text-light); overflow-x: hidden; -webkit-font-smoothing: antialiased; }
  .article-root ::selection { background: var(--spotlight); color: var(--wing); }
  .notfound-wrap {
    min-height: 100vh; display: flex; flex-direction: column;
    align-items: center; justify-content: center; background: #1B2B30;
  }

  .display { font-family: 'Cormorant', Georgia, serif; }
  .body-text { font-family: 'Source Serif 4', Georgia, serif; }
  .utility { font-family: 'DM Sans', system-ui, sans-serif; }

  .reveal {
    opacity: 0; transform: translateY(28px);
    transition: opacity 0.8s cubic-bezier(0.16,1,0.3,1), transform 0.8s cubic-bezier(0.16,1,0.3,1);
  }
  .reveal.visible { opacity: 1; transform: translateY(0); }
  .reveal-delay-1 { transition-delay: 0.12s; }
  .reveal-delay-2 { transition-delay: 0.24s; }

  .hero {
    min-height: 100vh; display: flex; flex-direction: column; justify-content: flex-end;
    padding: 0 clamp(24px,6vw,120px) clamp(60px,10vh,120px);
    background: linear-gradient(180deg, #111E22 0%, var(--wing) 100%);
    position: relative;
  }
  .hero::before {
    content: ''; position: absolute; inset: 0;
    background: radial-gradient(ellipse 80% 50% at 30% 70%, rgba(176,141,87,0.06) 0%, transparent 70%);
    pointer-events: none;
  }
  .hero-overline {
    font-size: clamp(11px,1.2vw,13px); font-weight: 500;
    letter-spacing: 0.2em; text-transform: uppercase;
    color: var(--spotlight); margin-bottom: clamp(20px,3vh,36px);
  }
  .hero-title {
    font-size: clamp(42px,8vw,96px); font-weight: 300;
    line-height: 1.0; letter-spacing: -0.02em;
    color: var(--text-light); max-width: 900px; margin-bottom: clamp(16px,2vh,28px);
  }
  .hero-title em { font-style: italic; font-weight: 400; color: var(--spotlight); }
  .hero-subtitle {
    font-size: clamp(16px,2.2vw,22px); font-weight: 300;
    font-style: italic; line-height: 1.5;
    color: var(--smoke); max-width: 520px;
  }

  .lede-section { background: var(--wing); padding: clamp(48px,8vh,100px) clamp(24px,6vw,120px); }
  .lede-text {
    font-size: clamp(19px,2.4vw,24px); font-weight: 300;
    line-height: 1.75; color: var(--text-light);
    max-width: 660px; margin-bottom: 1.4em;
  }
  .lede-text:last-child { margin-bottom: 0; }
  .lede-text em { font-style: italic; color: var(--warm-patch); }
  .lede-text strong { font-weight: 500; color: #fff; }

  .crossfade-to-light {
    height: clamp(80px,12vh,160px);
    background: linear-gradient(180deg, var(--wing) 0%, var(--gauze) 100%);
  }
  .crossfade-to-dark {
    height: clamp(80px,12vh,160px);
    background: linear-gradient(180deg, var(--gauze) 0%, var(--wing) 100%);
  }

  .section-light {
    background: var(--gauze); color: var(--text-dark);
    padding: clamp(40px,6vh,80px) clamp(24px,6vw,120px);
  }
  .section-dark {
    background: var(--wing); color: var(--text-light);
    padding: clamp(40px,6vh,80px) clamp(24px,6vw,120px);
  }

  .act-number {
    font-size: clamp(11px,1.2vw,13px); font-weight: 500;
    letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: 16px;
  }
  .section-light .act-number { color: var(--gel); }
  .section-dark .act-number { color: var(--spotlight); }

  .section-title {
    font-size: clamp(28px,5vw,48px); font-weight: 300;
    line-height: 1.15; letter-spacing: -0.01em;
    margin-bottom: clamp(28px,4vh,48px); max-width: 600px;
  }
  .section-light .section-title { color: var(--wing); }
  .section-dark .section-title { color: var(--text-light); }

  .prose {
    font-size: clamp(17px,1.8vw,19px); font-weight: 400;
    line-height: 1.8; max-width: 620px; margin-bottom: 1.5em;
  }
  .prose:last-child { margin-bottom: 0; }
  .section-light .prose { color: #3A3832; }
  .section-dark .prose { color: var(--text-light); }
  .prose em { font-style: italic; }
  .section-dark .prose em { color: var(--warm-patch); }
  .section-light .prose em { color: var(--gel); }

  .pull-quote {
    margin: clamp(36px,6vh,72px) 0;
    padding-left: clamp(20px,3vw,40px);
    border-left: 2px solid var(--spotlight); max-width: 580px;
  }
  .pull-quote-text {
    font-size: clamp(22px,3.5vw,34px); font-weight: 300;
    font-style: italic; line-height: 1.45; letter-spacing: -0.01em;
  }
  .section-light .pull-quote-text { color: var(--wing); }
  .section-dark .pull-quote-text { color: var(--warm-patch); }
  .pull-quote-attr {
    margin-top: 14px; font-size: 13px; font-weight: 500;
    letter-spacing: 0.08em; text-transform: uppercase;
  }
  .section-light .pull-quote-attr { color: var(--gel); }
  .section-dark .pull-quote-attr { color: var(--spotlight); }

  .scene-mark {
    display: flex; align-items: center; gap: 16px;
    margin: clamp(40px,6vh,72px) 0;
  }
  .scene-mark::before, .scene-mark::after {
    content: ''; flex: 1; height: 1px; max-width: 60px;
  }
  .section-light .scene-mark::before, .section-light .scene-mark::after { background: var(--smoke); }
  .section-dark .scene-mark::before, .section-dark .scene-mark::after { background: rgba(216,211,202,0.2); }
  .scene-mark-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--spotlight); }

  .coda {
    background: var(--wing);
    padding: clamp(60px,10vh,120px) clamp(24px,6vw,120px);
    border-top: 1px solid rgba(176,141,87,0.15);
  }
  .coda-text {
    font-size: clamp(20px,3vw,28px); font-weight: 300;
    line-height: 1.65; color: var(--text-light);
    max-width: 640px; margin-bottom: 1.3em;
  }
  .coda-text:last-child { margin-bottom: 0; }
  .coda-text em { color: var(--warm-patch); font-style: italic; }

  .article-footer {
    background: var(--wing);
    padding: clamp(32px,5vh,60px) clamp(24px,6vw,120px);
    border-top: 1px solid rgba(216,211,202,0.08);
    display: flex; justify-content: space-between; align-items: baseline;
    flex-wrap: wrap; gap: 16px;
  }
  .footer-byline {
    font-size: 12px; font-weight: 400;
    letter-spacing: 0.08em; text-transform: uppercase; color: var(--smoke);
  }
  .footer-back {
    font-size: 13px; color: var(--spotlight);
    text-decoration: none; letter-spacing: 0.04em; transition: color 0.2s;
  }
  .footer-back:hover { color: var(--warm-patch); }

  @media (max-width: 600px) {
    .hero { justify-content: center; min-height: 90vh; }
    .pull-quote { padding-left: 16px; }
  }
`;
