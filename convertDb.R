#!/usr/bin/env Rscript

library(methods)
library(jsonlite)


changeSuffix <- function(fname, suff) {
    parts <- strsplit(fname, "\\.")[[1]]
    if (length(parts) == 0) {
        parts <- c("Untitled", suff)
    } else if (length(parts) == 1) {
        parts <- c(parts[1], suff)
    } else {
        parts[length(parts)] = suff
    }
    return(paste(parts, collapse="."))
}

JSON_DIR = "json"

for (subdir in c("db", "logs")) {

    dirname <- file.path(JSON_DIR, subdir)

    for (f in list.files(path=dirname, "^.*\\.json$")) {
        jsonFile <- file.path(dirname, f)
        csvFile <- file.path(subdir, changeSuffix(f, "csv"))
        json <- readChar(jsonFile, file.info(jsonFile)$size)
        df <- fromJSON(json)
        if (!file.exists(subdir))
            dir.create(subdir)
        write.csv(df, csvFile, row.names=F)
    }
}
