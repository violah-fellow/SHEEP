library(tidyverse)


# Load files to compare
training <- read_csv("Patents/Patents_Data/patents_subest_for_pipeline_testing2.csv")
result <- read_csv("Pipeline/Patents/data/patents_training_results2.csv")

training <- training %>%
    dplyr::select(id, family_id, scope, pillar)
result <- result %>%
    dplyr::select(id, scope_LLM, confidence_LLM, pred_combined, proba_scope, pillar_LLM, pred_pillar)

full <- training %>%
    left_join(result, by = "id")

write_csv(comb %>% select(
    scope, pillar, scope_LLM, confidence_LLM,
    proba_scope, pred_pillar, pred_combined,
    scope_curated
), "Patents/Patents_Data/Training_results_full2.csv")

## Scenario 2
comb <- training %>%
    left_join(result, by = "id") %>%
    filter(!is.na(proba_scope)) %>%
    mutate(scope_curated = ifelse((is.na(scope_LLM) & pred_combined == "in"), "manual_review",
        ifelse((confidence_LLM >= 5 & (!is.na(pillar_LLM) | !is.na(pred_pillar))) | (confidence_LLM %in% c(3, 4) & proba_scope > 0.8 & (!is.na(pillar_LLM) | !is.na(pred_pillar))) | (confidence_LLM == 2 & proba_scope > 0.9 & (!is.na(pillar_LLM) | !is.na(pred_pillar))), "in",
            ifelse((scope_LLM == "out" & confidence_LLM %in% c(1, 2) & proba_scope < 0.6 & is.na(pillar_LLM)), "out", "manual_review")
        )
    )) %>%
    mutate(scope_curated = ifelse(pred_combined == "out", "out", scope_curated))

## Claude scenario
comb <- training %>%
    left_join(result, by = "id") %>%
    filter(!is.na(proba_scope)) %>%
    mutate(scope_curated = case_when(
        # Scope_LLM missing + ML says in → manual review
        is.na(scope_LLM) & pred_combined == "in" ~ "manual_review",

        # LLM says in with high confidence → always auto-in (no pillar required)
        scope_LLM == "in" & confidence_LLM >= 5 ~ "in",

        # LLM uncertain/in + ML confirms + pillar assigned
        confidence_LLM <= 4 & proba_scope > 0.8 & !is.na(pred_pillar) ~ "in",

        # LLM says out, ML agrees, no pillar assigned → auto-out
        scope_LLM == "out" & confidence_LLM %in% c(1, 2) & proba_scope < 0.6 & is.na(pred_pillar) ~ "out",

        # Everything else → manual review
        TRUE ~ "manual_review"
    )) %>%
    mutate(scope_curated = ifelse(pred_combined == "out", "out", scope_curated))

# like for publications
comb <- training %>%
    left_join(result, by = "id") %>%
    filter(!is.na(proba_scope)) %>%
    mutate(scope_curated = ifelse((is.na(scope_LLM) & pred_combined == "in"), "manual_review", ifelse((scope_LLM == "in" & confidence_LLM > 4 & !is.na(pillar_LLM)) |
        (scope_LLM == "in" & confidence_LLM == 4 & !is.na(pillar_LLM) & pillar_LLM == pred_pillar), "in",
    ifelse((scope_LLM == "out" & confidence_LLM < 2 & is.na(pillar_LLM)), "out", "manual_review")
    )))


## results
comb %>%
    # dplyr::filter(!is.na(scope_curated)) %>%
    mutate(scope_match = scope == scope_curated) %>%
    select(id, scope, scope_curated, scope_match, everything()) %>%
    group_by(scope, scope_curated) %>%
    summarise(n = n()) %>%
    ungroup() %>%
    mutate(f = n / sum(n)) %>%
    group_by(scope) %>%
    mutate(sum = sum(n))

# Match scope overall
# TRUE 85, FALSE 38
# ratio: 85 / (85+38)

# Match pillar to scope
comb <- comb %>%
    mutate(pillar_curated = ifelse(scope_curated == "out", NA,
        ifelse(!is.na(pillar_LLM), pillar_LLM,
            ifelse(!is.na(pred_pillar), pred_pillar, NA)
        )
    ))


# Match pillar overall
comb %>%
    dplyr::filter(!is.na(pillar_curated)) %>%
    mutate(pillar_match = pillar == pillar_curated) %>%
    select(id, pillar, pillar_curated, pillar_match, everything()) %>%
    group_by(pillar, pillar_curated) %>%
    summarise(n = n()) %>%
    group_by(pillar) %>%
    mutate(f = n / sum(n))

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
