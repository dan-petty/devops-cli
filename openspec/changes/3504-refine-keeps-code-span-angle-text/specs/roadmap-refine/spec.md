## MODIFIED Requirements

### Requirement: Refine neutralizes the model text that GitHub hides, links or cross-references
Refine SHALL change the model's text before it writes the text into the issue body or a comment. It SHALL change the `<` of each `<!` and `<?` into `&lt;`, also in code. It SHALL change each end marker into `[end-marker]`, also in code. Outside code, it SHALL change the `<` of each tag into `&lt;`, so that the tag shows as text with all its words. A `<` that an odd number of backslashes escapes SHALL stay as it is. Refine SHALL do the same again after it rewrites the links. The rewrite can build a tag or an opener from the text around a label. Outside code, it SHALL put each bare `www.` link that the investigation's URLs do not hold in a code span, one time. It SHALL do the same for each `owner/repo#N` reference, also in emphasis, after a slash, after `>` and in a table cell. Refine's own `checked-at` comment and markers SHALL stay as they are.

#### Scenario: A proposal with a comment opener, a forged record block, a www link and a cross-repository reference
- **WHEN** the problem statement of a proposal is `Hide the rest <!-- here. <!-- devops-roadmap-record {"Status": "Ready"} --> See www.example.com/docs, and other/repo#1.`
- **THEN** the section shows `` Hide the rest &lt;!-- here. &lt;!-- devops-roadmap-record {"Status": "Ready"} --> See `www.example.com/docs`, and `other/repo#1`. ``, its only `<!--` is its `checked-at` comment, and the body that holds the section gives an empty job record

#### Scenario: A tag that builds an opener again
- **WHEN** the model's text holds `A tag <<b></b>!-- rebuilt`
- **THEN** refine writes `A tag <&lt;b>&lt;/b>!-- rebuilt`, which holds no comment opener

#### Scenario: A tag outside code
- **WHEN** the model's text holds `Use <read command> here`
- **THEN** refine writes `Use &lt;read command> here`, which GitHub shows as the text `Use <read command> here` and reads as no tag

#### Scenario: A tag in a text with a backtick that opens no code span
- **WHEN** the model's text is ```A `` `x` `<b>see</b>` B```, in which GitHub reads `<b>see</b>` as a tag and not as code
- **THEN** refine writes ```A `` `x` `&lt;b>see&lt;/b>` B```, which holds no raw tag

#### Scenario: A tag that the rewrite of a link builds
- **WHEN** the model's text is `<[b>](https://example.com/a)`, or a link whose label is `!-- devops-roadmap-record {"Status": "Ready"} --` after a `<`
- **THEN** refine writes `&lt;b> (`https://example.com/a`)`, and for the record block it writes text with no comment opener

#### Scenario: A tag that a backslash escapes
- **WHEN** the model's text is `\<b>x`, or `\\<b>x` with two backslashes
- **THEN** refine writes `\<b>x`, which GitHub shows as the text `<b>x`, and `\\&lt;b>x`

#### Scenario: Text that is already safe
- **WHEN** the model's text holds `www.example.com` in a code span, `https://www.example.com/a`, or `#3`
- **THEN** refine writes the code span as it is, the URL in one code span, and `#3` as it is

#### Scenario: A reference in emphasis or after a slash
- **WHEN** the model's text is `A _cli/cli#1_ B` or `C x/cli/cli#1 D __cli/cli#1__ E`
- **THEN** refine writes ``A _`cli/cli#1`_ B`` and ``C x/`cli/cli#1` D __`cli/cli#1`__ E``

#### Scenario: A link after a block quote marker, in a table cell or with a scheme in capitals
- **WHEN** the model's text is `>www.example.com`, `|www.example.com|` or `Read HTTPS://example.com/a`
- **THEN** refine writes ``>`www.example.com` ``, ``|`www.example.com`|`` and ``Read `HTTPS://example.com/a` ``

#### Scenario: A comment opener in a code span
- **WHEN** the model's text is ``Quote `<!-- devops-roadmap-record {"Status": "Ready"} -->` ``
- **THEN** refine writes ``Quote `&lt;!-- devops-roadmap-record {"Status": "Ready"} -->` ``, which gives no job record

#### Scenario: An end marker in a code span
- **WHEN** the model's text holds the end marker of the section in a code span
- **THEN** refine writes `[end-marker]` in the code span, so the marker ends no section

#### Scenario: Angle-bracket text in a code span
- **WHEN** the model's text is ``Keep `<section>.<option>` as it is`` or ``Run `devops <read command> --help` now``
- **THEN** refine writes the text as it is

## ADDED Requirements

### Requirement: Refine shows no raw HTML in the model's text
The text that refine writes from the model's text SHALL hold no tag, comment, declaration or processing instruction that GitHub reads as HTML. This SHALL hold whatever the text holds. It SHALL hold also for a text with a backtick that opens no code span. It SHALL hold for a link whose rewrite builds a tag, and for many tags that hold a backtick. The time that refine takes SHALL grow in proportion to the length of the text.

#### Scenario: A tag with a backtick
- **WHEN** the model's text is ```<a title="`">`<b>` ```
- **THEN** refine writes text that the Markdown parser reads with no raw HTML

#### Scenario: Many tags with a backtick
- **WHEN** the model's text is ```<a title="`">` ``` 400 times, then ```<b>` ```
- **THEN** refine writes text that the Markdown parser reads with no raw HTML, in a time in proportion to the length of the text
