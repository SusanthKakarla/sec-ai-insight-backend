


#example curl commands 


# fetching apple 10k (large document)
"curl http://localhost:8000/api/v1/filings/320193/0000320193-24-000123/text"

#fetching apple (small document)
"curl http://localhost:8000/api/v1/filings/320193/0000320193-25-000044/text"




"curl http://localhost:8000/api/v1/filings/320193/0000320193-24-000123/analyze"


"curl http://localhost:8000/api/v1/filings/320193/0000320193-25-000044/analyze"


#run command 
"uvicorn app:app --host 0.0.0.0 --port 8000"
"uvicorn src.app:app --reload"


#search endpoint test 
"http://localhost:8000/api/companies/search?query=A"