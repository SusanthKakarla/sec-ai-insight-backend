


#example curl commands 


# fetching apple 10k (large document)
"curl http://localhost:8000/api/v1/filings/320193/0000320193-24-000123/text"
<!-- https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm#i7bfbfbe54b9647b1b4ba4ff4e0aba09d_268 -->


#fetching apple (small document)
"curl http://localhost:8000/api/v1/filings/320193/0000320193-25-000044/text"

#form PX14A6N
http://localhost:8000/api/analysis/0000320193/0001377739-22-000005



"curl http://localhost:8000/api/v1/filings/320193/0000320193-24-000123/analyze"


"curl http://localhost:8000/api/v1/filings/320193/0000320193-25-000044/analyze"


#run command 
"uvicorn app:app --host 0.0.0.0 --port 8000"
"uvicorn src.app:app --reload"


#search endpoint test 
"http://localhost:8000/api/companies/search?query=A"



<!-- helpers -->
memwalker  -> https://github.com/orgs/alphanome-ai/discussions/18
secparser -> https://github.com/alphanome-ai/sec-parser?tab=readme-ov-file