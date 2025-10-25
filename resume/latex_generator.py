from models import ResumeData, SkillCategory, Project, Experience


class LatexGenerator:
    def __init__(self):
        pass
    
    def escape_latex_special_chars(self, text: str) -> str:
        """Escape special LaTeX characters in text"""
        # Replace special characters that cause LaTeX issues
        replacements = {
            '&': '\\&',
            '%': '\\%',
            '$': '\\$',
            '#': '\\#',
            '^': '\\textasciicircum{}',
            '_': '\\_',
            '{': '\\{',
            '}': '\\}',
            '~': '\\textasciitilde{}'
        }
        
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        return text

    def convert_json_to_latex(self, resume_data: ResumeData) -> str:
        """Convert JSON resume data to LaTeX using the original template format"""
        try:
            # Read the original template
            with open("resources/resume_original.tex", "r", encoding="utf-8") as f:
                latex_content = f.read()

            # Replace the profile section content only
            profile_start = latex_content.find("\\section{PROFILE}")
            if profile_start != -1:
                # Find the opening brace after PROFILE (should be the content brace)
                profile_brace_start = latex_content.find("{", profile_start)
                if profile_brace_start != -1:
                    # Find the next opening brace (this should be the content)
                    content_start = latex_content.find("{", profile_brace_start + 1)
                    if content_start != -1:
                        # Find the closing brace for the profile content
                        content_end = latex_content.find("}", content_start)
                        if content_end != -1:
                            latex_content = (latex_content[:content_start + 1] + 
                                           self.escape_latex_special_chars(resume_data.profile) + 
                                           latex_content[content_end:])
            
            # Replace the projects section
            projects_comment_start = latex_content.find("%-----------PROJECTS-----------")
            if projects_comment_start != -1:
                # Find the end of the projects section (before TECHNICAL SKILLS)
                skills_start = latex_content.find("\\section{TECHNICAL SKILLS}")
                if skills_start != -1:
                    # Build new projects section
                    new_projects = """
%-----------PROJECTS-----------
\\vspace{+5pt}
\\section{PROJECTS}
    \\vspace{-5pt}
    \\resumeSubHeadingListStart
"""
                    for project in resume_data.projects:
                        github_links = ""
                        if project.github_links and project.github_link_names:
                            # Generate multiple GitHub links with custom names
                            link_parts = []
                            for i, (link, name) in enumerate(zip(project.github_links, project.github_link_names)):
                                link_parts.append("\\href{" + link + "}{\\large{\\underline{" + name + "}" + "}" + "}")
                            github_links = " $|$ " + " ".join(link_parts)
                        
                        new_projects += """
      \\resumeProjectHeading
          {\\textbf{\\large{""" + self.escape_latex_special_chars(project.name) + """}}""" + github_links + """}{""" + project.date + """}
          \\resumeItemListStart"""
                        
                        for bullet in project.bullet_points:
                            new_projects += """
            \\resumeItem{\\normalsize{""" + self.escape_latex_special_chars(bullet) + """}}"""
                        
                        new_projects += """
          \\resumeItemListEnd
          \\vspace{-13pt}
"""
                    
                    new_projects += """
    \\resumeSubHeadingListEnd
"""
                    
                    # Replace the projects section
                    latex_content = latex_content[:projects_comment_start] + new_projects + latex_content[skills_start:]
            
            # Replace the technical skills section
            skills_section_start = latex_content.find("\\section{TECHNICAL SKILLS}")
            if skills_section_start != -1:
                # Find the end of the skills section (before EXPERIENCE)
                experience_start = latex_content.find("\\section{EXPERIENCE}")
                if experience_start != -1:
                    # Build new skills section
                    new_skills = """
%-----------PROGRAMMING SKILLS-----------
\\vspace{+5pt}
\\section{TECHNICAL SKILLS}
 \\begin{itemize}[leftmargin=0.15in, label={}]
    \\small{\\item{"""
                    
                    for skill_category in resume_data.skills:
                        skills_list = ", ".join([self.escape_latex_special_chars(skill) for skill in skill_category.skills])
                        new_skills += """
     \\textbf{\\normalsize{""" + self.escape_latex_special_chars(skill_category.name) + ":}}{\\normalsize{" + skills_list + "}} \\\\"""
                    
                    new_skills += """
    }}
 \\end{itemize}
 \\vspace{-15pt}
"""
                    
                    # Replace the skills section
                    latex_content = latex_content[:skills_section_start] + new_skills + latex_content[experience_start:]
            
            # Replace the experience section
            experience_comment_start = latex_content.find("%-----------EXPERIENCE-----------")
            if experience_comment_start != -1:
                # Find the end of the document
                document_end = latex_content.find("\\end{document}")
                if document_end != -1:
                    # Build new experience section
                    new_experience = """
%-----------EXPERIENCE-----------
\\vspace{+5pt}
\\section{EXPERIENCE}
  \\resumeSubHeadingListStart
"""
                    for exp in resume_data.experiences:
                        new_experience += """
    \\resumeSubheading
      {""" + self.escape_latex_special_chars(exp.company_name) + """}{""" + exp.start_date + """ -- """ + exp.end_date + """} 
      {""" + self.escape_latex_special_chars(exp.job_title) + """}{""" + self.escape_latex_special_chars(exp.location) + """}
      \\resumeItemListStart"""
                        
                        for bullet in exp.bullet_points:
                            new_experience += """
        \\resumeItem{\\normalsize{""" + self.escape_latex_special_chars(bullet) + """}}"""
                        
                        new_experience += """
      \\resumeItemListEnd  
"""
                    
                    new_experience += """
  \\resumeSubHeadingListEnd
\\vspace{-12pt}
"""
                    
                    # Replace the experience section
                    latex_content = latex_content[:experience_comment_start] + new_experience + latex_content[document_end:]
            
            return latex_content
            
        except Exception as e:
            print(f"Error creating LaTeX content: {str(e)}")
            return None
