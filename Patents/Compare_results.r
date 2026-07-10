library(tidyverse)


# Load files to compare
training <- read_csv("Patents/Patents_Data/patents_subest_for_pipeline_testing.csv")
result <- read_csv("Pipeline/Patents/data/patents_training_results.csv")

training <- training %>%
    dplyr::select(id, family_id, scope, pillar)
result <- result %>%
    dplyr::select(id, scope_curated, scope_LLM, confidence_LLM, pred_scope, pred_combined, proba_scope, pillar_curated, pillar_LLM, pred_pillar)

full <- training %>%
    left_join(result, by = "id")

## BEFORE manual review (LLM only)
comb <- training %>%
    left_join(result, by = "id") %>%
    filter(!is.na(pred_scope)) %>%
    mutate(scope_curated = ifelse((confidence_LLM)))

# like for publications
mutate(scope_curated = ifelse((is.na(scope_LLM) & pred_combined == "in"), "manual_review", ifelse((scope_LLM == "in" & confidence_LLM > 4 & !is.na(pillar_LLM)) |
    (scope_LLM == "in" & confidence_LLM == 4 & !is.na(pillar_LLM) & pillar_LLM == pred_pillar), "in",
ifelse((scope_LLM == "out" & confidence_LLM < 2 & is.na(pillar_LLM)), "out", "manual_review")
)))

comb %>%
    # dplyr::filter(!is.na(scope_curated)) %>%
    mutate(scope_match = scope == scope_curated) %>%
    select(id, scope, scope_curated, scope_match, everything()) %>%
    group_by(scope, scope_curated) %>%
    summarise(n = n()) %>%
    ungroup() %>%
    mutate(f = n / sum(n))

# Match scope overall
# TRUE 85, FALSE 38
# ratio: 85 / (85+38)

comb %>%
    filter(scope_LLM != scope)


# Match pillar overall
comb %>%
    dplyr::filter(!is.na(pillar_curated)) %>%
    mutate(pillar_match = pillar == pillar_curated) %>%
    select(id, pillar, pillar_curated, pillar_match, everything()) %>%
    group_by(pillar_match) %>%
    summarise(n = n())

# FALSE           10
# TRUE            73
# ratio = 87.9%

comb %>%
    filter(!is.na(proba_scope)) %>%
    mutate(scope_LLM = replace_na(scope_LLM, "out")) %>%
    mutate(scope_new = ifelse(scope_LLM == "in" | proba_scope > 0.8, "in", "out")) %>%
    mutate(scope_match = scope == scope_new) %>%
    select(id, scope, scope_new, scope_match, proba_scope, everything()) %>%
    group_by(scope_match) %>%
    summarise(n = n())

t <- full %>%
    dplyr::filter(confidence_LLM == 2) %>%
    arrange(scope, proba_scope)

view(t)




# Publications


# Load files to compare
training <- read_csv("Publications/Publications_Data/publications_subset_for_pipeline_testing.csv")
result <- read_csv("Pipeline/Publications/data/publications_training_results.csv")

training <- training %>%
    dplyr::select(id, scope, pillar)
result <- result %>%
    dplyr::select(id, scope_curated, scope_LLM, confidence_LLM, pred_combined, pillar_curated, pillar_LLM, pred_pillar)

full <- training %>%
    left_join(result, by = "id")

## BEFORE manual review (LLM only)
comb <- training %>%
    left_join(result, by = "id") %>%
    dplyr::filter(!is.na(pred_combined)) %>%
    # filter(pred_combined == "in") %>%
    mutate(scope_curated = ifelse((is.na(scope_LLM) & pred_combined == "in"), "manual_review", ifelse((scope_LLM == "in" & confidence_LLM > 4 & !is.na(pillar_LLM)) |
        (scope_LLM == "in" & confidence_LLM == 4 & !is.na(pillar_LLM) & pillar_LLM == pred_pillar), "in",
    ifelse((scope_LLM == "out" & confidence_LLM < 3 & is.na(pillar_LLM)), "out", "manual_review")
    )))

comb %>%
    dplyr::filter(!is.na(scope_curated)) %>%
    filter(scope_curated != "manual_review") %>%
    mutate(scope_match = scope == scope_curated) %>%
    select(id, scope, scope_curated, scope_match, everything()) %>%
    group_by(scope, scope_curated) %>%
    summarise(n = n()) %>%
    group_by(scope) %>%
    mutate(fr = n / sum(n))

comb %>%
    group_by(scope, pred_combined, scope_curated) %>%
    summarise(n = n()) %>%
    ungroup() %>%
    group_by(scope) %>%
    mutate(sum = sum(n))


# Match scope overall
# TRUE 139, FALSE 15
# ratio: 90%

comb %>%
    dplyr::filter(!is.na(pillar_LLM)) %>%
    dplyr::filter(scope_curated == "in") %>%
    mutate(pillar_match = pillar == pillar_LLM) %>%
    select(id, pillar, pillar_curated, pillar_match, everything()) %>%
    group_by(pillar, pillar_LLM) %>%
    summarise(n = n()) %>%
    group_by(pillar) %>%
    mutate(fr = n / sum(n))
