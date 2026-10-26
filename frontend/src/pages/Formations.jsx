import { useState, useMemo } from "react";

const q = (s) => encodeURIComponent(s);

const DOMAINES = {
  "Informatique / Développement": ["développeur web", "python", "cybersécurité"],
  "Data / IA": ["data analyst", "machine learning", "power bi"],
  "Marketing digital": ["marketing digital", "SEO", "community manager"],
  "Gestion / Finance": ["comptabilité", "finance d'entreprise", "excel avancé"],
  "Management de projet": ["gestion de projet", "scrum", "PMP"],
  "Design / UX": ["UX design", "figma", "graphisme"],
  "Réseaux / Cloud": ["réseaux cisco", "AWS", "azure"],
  "Langues / Soft skills": ["anglais professionnel", "communication", "leadership"],
};

const PLATEFORMES = [
  { nom: "Coursera", type: "Cours + certificats", url: (t) => `https://www.coursera.org/courses?query=${q(t)}` },
  { nom: "edX", type: "Cours universitaires", url: (t) => `https://www.edx.org/search?q=${q(t)}` },
  { nom: "OpenClassrooms", type: "Parcours en français", url: (t) => `https://openclassrooms.com/fr/search?q=${q(t)}` },
  { nom: "LinkedIn Learning", type: "Cours courts", url: (t) => `https://www.linkedin.com/learning/search?keywords=${q(t)}` },
  { nom: "Udemy", type: "Cours pratiques", url: (t) => `https://www.udemy.com/courses/search/?q=${q(t)}` },
  { nom: "YouTube", type: "Gratuit", url: (t) => `https://www.youtube.com/results?search_query=${q("formation " + t)}` },
];

const CERTIFS = {
  "Informatique / Développement": [
    ["freeCodeCamp", "https://www.freecodecamp.org/learn"],
    ["Microsoft Learn", "https://learn.microsoft.com/training/"],
  ],
  "Data / IA": [
    ["Google Data Analytics", "https://grow.google/certificates/"],
    ["Microsoft Learn (Power BI)", "https://learn.microsoft.com/training/"],
  ],
  "Marketing digital": [
    ["Google Skillshop", "https://skillshop.withgoogle.com/"],
    ["HubSpot Academy", "https://academy.hubspot.com/"],
  ],
  "Réseaux / Cloud": [
    ["Cisco Networking Academy", "https://www.netacad.com/"],
    ["AWS Skill Builder", "https://skillbuilder.aws/"],
  ],
  "Management de projet": [
    ["PMI", "https://www.pmi.org/certifications"],
    ["Scrum.org", "https://www.scrum.org/"],
  ],
};

export default function Formations() {
  const [domaine, setDomaine] = useState(Object.keys(DOMAINES)[0]);
  const [libre, setLibre] = useState("");
  const themes = useMemo(
    () => (libre.trim() ? [libre.trim()] : DOMAINES[domaine]),
    [domaine, libre]
  );

  return (
    <div style={{ padding: 24, maxWidth: 1000 }}>
      <h1 style={{ fontSize: 28, fontWeight: 700 }}>Formation & certification</h1>
      <p style={{ color: "#64748b" }}>
        Trouvez des formations et certifications adaptées à votre domaine.
      </p>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", margin: "16px 0" }}>
        <select
          value={domaine}
          onChange={(e) => { setDomaine(e.target.value); setLibre(""); }}
          style={{ padding: 10, borderRadius: 8, border: "1px solid #cbd5e1" }}
        >
          {Object.keys(DOMAINES).map((d) => <option key={d}>{d}</option>)}
        </select>
        <input
          value={libre}
          onChange={(e) => setLibre(e.target.value)}
          placeholder="Ou tapez un sujet (ex : SQL, Excel...)"
          style={{ padding: 10, borderRadius: 8, border: "1px solid #cbd5e1", minWidth: 260 }}
        />
      </div>

      {themes.map((t) => (
        <section key={t} style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, textTransform: "capitalize" }}>{t}</h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(220px,1fr))", gap: 12, marginTop: 8 }}>
            {PLATEFORMES.map((p) => (
              <a key={p.nom} href={p.url(t)} target="_blank" rel="noopener noreferrer"
                 style={{ padding: 14, border: "1px solid #e2e8f0", borderRadius: 12, textDecoration: "none", color: "inherit", background: "#fff" }}>
                <strong>{p.nom}</strong>
                <div style={{ fontSize: 13, color: "#64748b" }}>{p.type}</div>
              </a>
            ))}
          </div>
        </section>
      ))}

      {!libre && CERTIFS[domaine] && (
        <section>
          <h2 style={{ fontSize: 18, fontWeight: 600 }}>Certifications reconnues</h2>
          <ul style={{ marginTop: 8 }}>
            {CERTIFS[domaine].map(([nom, url]) => (
              <li key={nom}><a href={url} target="_blank" rel="noopener noreferrer">{nom}</a></li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}