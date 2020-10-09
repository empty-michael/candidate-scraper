# candidate-scraper
A small module for finding and rating political candidates running in state-level elections. 

* `get_state_elections_info()` finds state election urls on Ballotpedia. 
* `CandidateTable` builds a table of candidate info from election page and saves as JSON. 
  * Each candidate's campaign website is searched for keywords according to `WebsiteSearcher`
* `CandidateScorer` assigns scores to each keyword and totals the score for each candidate. 
