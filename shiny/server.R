
library(shiny)

Plans <- read.csv("Plans.csv", header=T)
AllLocations <- read.csv("AllLocations.csv", header=T)


shinyServer(function(input, output) {

  output$map <- renderLeaflet({
    map <- leaflet() %>% 
      addTiles() %>%
      setView(lat=40.4, lng=-76.5, zoom=7)
    byPlan <- split(AllLocations, AllLocations$plan_id)
    for (planId in names(byPlan)) {
      map <- map %>%
        addMarkers(data=byPlan[[planId]],
                   lng=~lng, lat=~lat,
                   label=~group_name,
                   popup=~group_href,
                   group=planId,
                   clusterOptions=markerClusterOptions()) %>%
        hideGroup(planId)
    }
    map
  })
  
  # Updates which plan's group should be visible
  observe({
    planId <- input$planId
    proxy <- leafletProxy("map")
    for (pid in Plans$plan_id) {
      if (pid == planId)
        proxy <- proxy %>% showGroup(pid)
      else
        proxy <- proxy %>% hideGroup(pid)
    }
  })
  
})
