
library(shiny)
library(knitr)
library(leaflet)

options(stringsAsFactors=F)

Plans <- read.csv("Plans.csv", header=T)
Plans$plan_type <- factor(Plans$plan_type, levels=unique(Plans$plan_type))

sapply(c("About.Rmd"), knit, quiet=T)


shinyUI(navbarPage(
  
  "Medical Groups and Group Practices", id="nav",
  
  tabPanel(
    "Map", 
    div(class="outer",
        tags$style(type="text/css", 
                   ".outer {position:fixed; top:41px; left:0; right:0; bottom:0; overflow:hidden; padding:0}"),
        leafletOutput("map", width="100%", height="100%"),
        absolutePanel(
          top=20, right=10,
          div(class="shinycontrols",
              tags$style(type="text/css",
                         ".shinycontrols {color:#2a52be; font-weight:bold}"),
              selectInput("planId", "Select Plan", 
                          lapply(split(Plans, Plans$plan_type), 
                                 function(x) { setNames(x$plan_id, x$plan_name) } )))))),
  
  tabPanel(
    "About",
    # https://github.com/rstudio/rmarkdown/issues/329
    tags$style(type="text/css",
               "code { color:inherit; background-color:rgba(0, 0, 0, 0.04) }"),
    withMathJax(), 
    includeMarkdown("About.md"))

))
