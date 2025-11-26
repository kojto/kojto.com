@echo off
setlocal EnableDelayedExpansion

:: Set output file name
set "output_file=combined_output.txt"
:: Set temporary file for table of contents
set "toc_temp=toc_temp.txt"

:: Clear the output file and TOC temp file if they already exist
if exist "%output_file%" del "%output_file%"
if exist "%toc_temp%" del "%toc_temp%"

:: Initialize counters
set "file_count=0"
set "xml_count=0"
set "py_count=0"
set "csv_count=0"

:: Log start of processing
echo Searching for .py, .xml, and .csv files in %CD% and subdirectories...

:: Loop through all .py, .xml, and .csv files in the current directory and subdirectories
for /r %%F in (*.py *.xml *.csv) do (
    echo Found: %%F
    echo Processing %%F...
    :: Add a header with the file path to the output file
    echo. >> "%output_file%"
    echo === Contents of %%F === >> "%output_file%"
    echo. >> "%output_file%"
    :: Append the file contents to the output file
    type "%%F" >> "%output_file%"
    echo. >> "%output_file%"
    :: Add file path to TOC temp file
    echo %%F >> "%toc_temp%"
    :: Increment file counter
    set /a file_count+=1
    :: Track .py, .xml, and .csv files separately
    if /i "%%~xF"==".py" set /a py_count+=1
    if /i "%%~xF"==".xml" set /a xml_count+=1
    if /i "%%~xF"==".csv" set /a csv_count+=1
)

:: Check if any files were found and processed
if not exist "%output_file%" (
    echo No .py, .xml, or .csv files found in the current directory or its subdirectories.
    echo Check: Are there any .py, .xml, or .csv files? Are file extensions correct (e.g., not .XML or .csvx)?
    if exist "%toc_temp%" del "%toc_temp%"
    pause
    exit /b
)

:: Append Table of Contents to the output file
echo. >> "%output_file%"
echo === Table of Contents === >> "%output_file%"
echo. >> "%output_file%"
set "index=1"
for /f "tokens=*" %%T in (%toc_temp%) do (
    echo !index!. %%T >> "%output_file%"
    set /a index+=1
)
echo. >> "%output_file%"
echo Total files combined: %file_count% (%py_count% .py, %xml_count% .xml, %csv_count% .csv) >> "%output_file%"

:: Clean up temporary TOC file
if exist "%toc_temp%" del "%toc_temp%"

echo All files have been combined into %output_file%.
echo Processed %file_count% files (%py_count% .py, %xml_count% .xml, %csv_count% .csv).
pause