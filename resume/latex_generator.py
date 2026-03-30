"""Build resume .tex from JSON + `resources/resume_original.tex`.

The template contains paired markers (one pair per injectable region):

    % resume-generator:begin <tag>
    % resume-generator:end <tag>

Everything from the ``begin`` line through the ``end`` line (inclusive) is
replaced by generated LaTeX. Static content (preamble, heading, education)
lives only in the .tex file — no duplicate bodies to maintain in Python.
"""

from __future__ import annotations

from pathlib import Path

from models import ResumeData

_TEMPLATE_PATH = Path(__file__).resolve().parent / "resources" / "resume_original.tex"


def _line_start(s: str, idx: int) -> int:
    prev = s.rfind("\n", 0, idx)
    return 0 if prev == -1 else prev + 1


def _line_end_after(s: str, idx: int) -> int:
    n = s.find("\n", idx)
    return len(s) if n == -1 else n + 1


def _replace_marked_block(tex: str, tag: str, body: str, *, path: Path) -> str:
    begin = f"% resume-generator:begin {tag}"
    end = f"% resume-generator:end {tag}"
    i = tex.find(begin)
    if i == -1:
        raise ValueError(f"Template {path} missing {begin!r}")
    j = tex.find(end, i + len(begin))
    if j == -1:
        raise ValueError(f"Template {path} missing {end!r} after {begin!r}")
    ls = _line_start(tex, i)
    le = _line_end_after(tex, j)
    if not body.endswith("\n"):
        body += "\n"
    return tex[:ls] + body + tex[le:]


class LatexGenerator:
    def escape_latex_special_chars(self, text: str) -> str:
        replacements = {
            "&": "\\&",
            "%": "\\%",
            "$": "\\$",
            "#": "\\#",
            "^": "\\textasciicircum{}",
            "_": "\\_",
            "{": "\\{",
            "}": "\\}",
            "~": "\\textasciitilde{}",
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        return text

    def _e(self, text: str) -> str:
        return self.escape_latex_special_chars(text)

    def _github_link_tex(self, link: str, label: str) -> str:
        return r"\href{" + link + r"}{\large{\underline{" + self._e(label) + r"}}}"

    def convert_json_to_latex(self, resume_data: ResumeData) -> str | None:
        try:
            tex = _TEMPLATE_PATH.read_text(encoding="utf-8")
        except OSError as e:
            print(f"Error reading resume template {_TEMPLATE_PATH}: {e}")
            return None

        try:
            tex = _replace_marked_block(
                tex, "profile", self._render_profile(resume_data), path=_TEMPLATE_PATH
            )
            tex = _replace_marked_block(
                tex, "projects", self._render_projects(resume_data), path=_TEMPLATE_PATH
            )
            tex = _replace_marked_block(
                tex, "skills", self._render_skills(resume_data), path=_TEMPLATE_PATH
            )
            tex = _replace_marked_block(
                tex,
                "experience",
                self._render_experience(resume_data),
                path=_TEMPLATE_PATH,
            )
            return tex
        except ValueError as e:
            print(f"Error creating LaTeX content: {e}")
            return None

    def _render_profile(self, data: ResumeData) -> str:
        return (
            "%-----------PROFILE-----------\n"
            "\\section{PROFILE}\n"
            f"      {{{self._e(data.profile)}}}\n"
        )

    def _render_projects(self, data: ResumeData) -> str:
        lines = [
            "%-----------PROJECTS-----------",
            r"\vspace{+5pt}",
            r"\section{PROJECTS}",
            r"    \vspace{-5pt}",
            r"    \resumeSubHeadingListStart",
        ]
        for project in data.projects:
            github_suffix = ""
            if project.github_links and project.github_link_names:
                parts = [
                    self._github_link_tex(link, name)
                    for link, name in zip(project.github_links, project.github_link_names)
                ]
                github_suffix = " $|$ " + " ".join(parts)

            title = r"\textbf{\large{" + self._e(project.name) + "}}"
            lines.append(r"      \resumeProjectHeading")
            lines.append(
                "          {"
                + title
                + github_suffix
                + "}{"
                + project.date
                + "}"
            )
            lines.append(r"          \resumeItemListStart")
            for bullet in project.bullet_points:
                lines.append(
                    r"            \resumeItem{\normalsize{"
                    + self._e(bullet)
                    + r"}}"
                )
            lines.append(r"          \resumeItemListEnd")
            lines.append(r"          \vspace{-13pt}")

        lines.append(r"    \resumeSubHeadingListEnd")
        return "\n".join(lines) + "\n"

    def _render_skills(self, data: ResumeData) -> str:
        lines = [
            "%-----------PROGRAMMING SKILLS-----------",
            r"\vspace{+5pt}",
            r"\section{TECHNICAL SKILLS}",
            r" \begin{itemize}[leftmargin=0.15in, label={}]",
            r"    \small{\item{",
        ]
        for cat in data.skills:
            skills_list = ", ".join(self._e(s) for s in cat.skills)
            lines.append(
                r"     \textbf{\normalsize{"
                + self._e(cat.name)
                + r":}}{\normalsize{"
                + skills_list
                + r"}} \\"
            )
        lines.extend(
            [
                r"    }}",
                r" \end{itemize}",
                r" \vspace{-15pt}",
            ]
        )
        return "\n".join(lines) + "\n"

    def _render_experience(self, data: ResumeData) -> str:
        lines = [
            "%-----------EXPERIENCE-----------",
            r"\vspace{+5pt}",
            r"\section{EXPERIENCE}",
            r"  \resumeSubHeadingListStart",
        ]
        for exp in data.experiences:
            lines.append(r"    \resumeSubheading")
            lines.append(
                "      {"
                + self._e(exp.company_name)
                + "}{"
                + exp.start_date
                + " -- "
                + exp.end_date
                + "} "
            )
            lines.append(
                "      {"
                + self._e(exp.job_title)
                + "}{"
                + self._e(exp.location)
                + "}"
            )
            lines.append(r"      \resumeItemListStart")
            for bullet in exp.bullet_points:
                lines.append(
                    r"        \resumeItem{\normalsize{"
                    + self._e(bullet)
                    + r"}}"
                )
            lines.append(r"      \resumeItemListEnd  ")

        lines.extend(
            [
                r"  \resumeSubHeadingListEnd",
                r"\vspace{-12pt}",
            ]
        )
        return "\n".join(lines) + "\n"
