
## For `search-data` API

1.  **Invalid Symbol:** Test the API with an invalid symbol (e.g., "INVALID"). The API should return a 400 Bad Request error with a message indicating that the symbol is invalid.
2.  **Invalid Option Type:** Test the API with an invalid option type (e.g., "XX"). The API should return a 400 Bad Request error with a message indicating that the option type is invalid.
3.  **Invalid Strike Price:** Test the API with a non-positive strike price (e.g., 0 or -100). The API should return a 400 Bad Request error with a message indicating that the strike price must be positive.
4.  **Invalid Date Format:** Test the API with invalid date formats for `from_date`, `to_date`, and `expiry_date`. The API should return a 400 Bad Request error with a message indicating that the date format is invalid.
5.  **`from_date` Greater Than `to_date`:** Test the API with a `from_date` that is greater than the `to_date`. The API should return a 400 Bad Request error with a message indicating that `from_date` cannot be greater than `to_date`.
6.  **`year` Parameter Mismatch:** Test the API with a `year` parameter that does not match the year of the `from_date`. The API should return a 400 Bad Request error with a message indicating that the `year` parameter must match the `from_date` year.
7.  **No Data Found (Database and NSE):** Test the API with a date range and other parameters for which no data exists in either the database or NSE. The API should return a 404 Not Found error with a message indicating that no data was retrieved.
8.  **Data Only in Database:** Test the API with a date range and other parameters for which data exists only in the database. The API should return a 200 OK response with the data and a `source` value of `"database/{table_name}"`.
9.  **Data Only in NSE:** Test the API with a date range and other parameters for which data exists only in NSE. The API should return a 200 OK response with the data and a `source` value of `"nse"`.
10. **Data in Both Database and NSE (Duplicates):** Test the API with a date range and other parameters for which data exists in both the database and NSE, including duplicate records. The API should return a 200 OK response with the combined data (without duplicates) and a `source` value of `"combined"`.
11. **Large Date Range:** Test the API with a very large date range to ensure that it can handle a large number of records efficiently.
12. **Different Option Types (CE and PE):** Test the API with both "CE" (Call) and "PE" (Put) option types to ensure that it handles both types correctly.
13. **Different Strike Prices:** Test the API with different strike prices to ensure that it handles different price points correctly.
14. **Boundary Dates:** Test the API with dates at the beginning and end of a month or year to ensure that it handles boundary conditions correctly.
15. **Data with Missing Fields:** Test the API with data that has missing fields (e.g., missing `open`, `high`, `low`, `close` values) to ensure that it handles missing data gracefully.
