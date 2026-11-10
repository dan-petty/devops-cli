# Design

## Decisions

- **Add the units `days` and `weeks` to the existing pattern.**: The rule asks for the elapsed time, and a task of more than a day is stated in days.
- **Accept a number word from one to twelve, and `a` or `an`, only before a unit and after a space.**: A model writes "two days" or "a week". A word that is no number, such as "some days", still gives no count.
- **Keep the count of tokens as it is.**: The live run shows no fault in it.

## Rejected alternatives

- **Accept any text that holds the word `days`, `weeks` or `hours`.**: "some days" gives no cost, and rule 3 asks for a time that a person can add up.
- **Parse numbers in words with a library.**: No such library is installed or maintained in this project, and twelve words cover the plans that the log shows.
