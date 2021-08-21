- [ ] Add cache size management 
- [ ] Add test coverage
- [ ] Run test in Travis CI
- [ ] Config file to provider default search config
- [ ] Support multi line regex
- [ ] Make the output format of the log subcommand configurable. E.g. full,
  only-matched-lines
- [ ] support build filter --since
      could be based on exact date or number of days
- [ ] add --print-signature flag to log subcommand to print out the stored
      search signature of the query so that can be easily copied to a file

Done:
- [x] Pre validate regex coming from the command line
- [x] Validate values of --result as a wrong value leads to empty search
  result form Zuul
- [x] Support grep before, after, context lines
- [x] Allow repeating --file in logsearch
- [x] Allow repeating --job
- [x] Show build result table columns based on provided query parameters
- [x] Add subcommand for showing a single build metadata
- [x] Re-print filtered build table based on grep results
- [x] Config file to define job categories (e.g. devstack based jobs) that can
  be used in --job search
- [x] Config file to store named searches, and the ability to re-run the search
  by name. Similarly, how elastic re-check signature works.
- [x] Move all the args access to the Config object
- [x] Support job groups in stored search
