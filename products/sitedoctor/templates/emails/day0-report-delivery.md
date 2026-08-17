Trigger: immediately after someone submits their domain for a free audit.

---

Subject: Your SiteDoctor audit for {{domain}} is ready

Hi {{first_name}},

Your audit is done — score: {{score}}/100. Full report attached (PDF/Markdown).

Top {{n_critical}} issue(s) we'd fix first:
{{#each critical_issues}}
- {{this.label}} — {{this.detail}}
{{/each}}

Everything else, including what's already working well, is in the attached report.

If you'd like help fixing any of this, reply and we'll point you to a partner who can — no obligation either way.

{{sender_name}}

_You're receiving this because you requested a free audit for {{domain}} at {{landing_page_url}}. Reply "stop" any time to opt out of further emails._
