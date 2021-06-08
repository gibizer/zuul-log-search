- [ ] Add cache size management 
- [ ] Add test coverage
- [ ] Run test in Travis CI
- [ ] Config file to provider default search config
- [ ] Config file to define job categories (e.g. devstack based jobs) that can
  be used in --job search
- [ ] Support multi line regex
- [ ] Re-print filtered build table based on grep results
- [ ] Add subcommand for showing a single build metadata
- [ ] Make the output format of the log subcommand configurable. E.g. full,
  only-matched-lines

Done:
- [x] Pre validate regex coming from the command line
- [x] Validate values of --result as a wrong value leads to empty search
  result form Zuul
- [x] Support grep before, after, context lines
- [x] Allow repeating --file in logsearch
- [x] Allow repeating --job
- [x] Show build result table columns based on provided query parameters
