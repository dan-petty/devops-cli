# Design

## Decisions

- **Part 1 of four.** The full design of #1127 does not fit one pull request, so the issue is split. This part has no command, no model call and no write to GitHub. The later parts call it. The module has callers only in tests until part 2 (#3740) adds the command. The alternative is to ship it with the command, and that is the pull request that #1127 could not hold.
- **`nearest` is a generic function over keys and vectors.** The intake planner keeps its entries and vectors, and passes the pairs. The sort is stable and reverse, so the order of equal scores is the order of the input, as before.
- **A shortlist is built for each open item as an anchor.** The members come from three signals. Each member keeps all the evidence that put it there, because the contest rule and the later model steps read it.
- **The strength order is fixed in an enum.** A shared path and identifier is strongest, because it points to the same code and the same name. Then a shared path, then a shared identifier, then a link, then an embedding rank. A link ranks low because a link can record a split on purpose, and the refutation pass of part 2 decides that.
- **A citation that many items share is ignored.** `CONTEXT.md`, `AGENTS.md` and a name such as `None` appear in many bodies. They do not show a shared cause. The cap is a count of open items, `DEFAULT_ROADMAP_CONSOLIDATE_COMMON_CITATION`. It is the same idea as a stop word list, with the corpus giving the list, so no word list needs a fix.
- **A shortlist holds at most `DEFAULT_ROADMAP_CONSOLIDATE_MEMBERS` members.** The strongest members stay, and a tie goes to the lower number. The model of part 2 reads the bodies, so the list must stay short.
- **An item is in one group at most.** `assign_groups` sorts every pair of an anchor and a member by the weight of the evidence, then by the lower anchor number, then by the lower member number. It places the pairs in that order. A pair is skipped when the member is in a group already, or when the anchor is a member of another group. So a contested item goes to the stronger evidence, a pair that two shortlists name (A lists B, and B lists A) is one group, and a member never anchors a group. The loop is the whole join: the code builds no graph and joins no group to another.
- **A shortlist with embedding evidence only is still a shortlist.** Every item has nearest neighbours, so most items get a weak shortlist. Part 2 (#3740) decides whether a weak shortlist is worth a model call. This part keeps the evidence, so that part 2 can tell the two apart.
- **A path that ends a sentence with a full stop is not read as a path.** `cited_paths` of refine does not match `src/a.py.` The shortlist uses that reader as the issue asks (#744 reads citations the same way), and the embedding signal still finds the pair. Changing the reader changes refine, so it is out of scope here.
- **The embedding cache keys on the hash of the person's text.** The key is `hash_text` of the title and the body outside the sections of refine and the alternatives job (`extract_section_and_outside`). A job that rewrites its own section does not cause a new embedding. The file also records the embedding model name, and a different name drops the file, because vectors of two models do not compare.
- **Citations and label lines read the text of a person only.** The refine section and the alternatives block are written by jobs and change at each refine run, so a path or an identifier that two of them share shows no shared cause. Only the "Dependencies" section is read from the whole body, because refine writes it on purpose (#2654).
- **The blocked-by count rides on the issue listing.** The listing already carries `issue_dependencies_summary`. A run reads the endpoint for the issues with a count above 0 only. For about 400 open issues, the run makes a few requests and not 400.
- **The blocked-by read returns the numbers of the issues in the same repository.** An issue of another repository that blocks an item is no item of this board.

## Rejected alternatives

- **One pull request for all of #1127.** The earlier refine round proposed four parts. The estimate is 180,000 tokens and 4 weeks, and the premise check found five stale points. One pull request cannot be reviewed with that scope.
- **Read the blocked-by endpoint for every open issue.** It makes one request for each issue and ignores the count that the listing gives.
- **GraphQL for the dependencies.** The REST endpoint exists and answers (see Feasibility), and the store reads REST listings with the session. A second transport adds a second set of fakes.
- **A union-find or networkx for transitive groups.** The issue says to make no transitive join. A shortlist for each anchor and a fixed tie-break are enough.
- **Hash the whole body.** The jobs of refine and the alternatives check write sections into the body. A weekly run would embed again each item that a job touched, with no change of the text of a person.
- **Cache by issue number.** An edit would then need a second check. The hash of the text answers both.
