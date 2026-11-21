# FX Rates Pipeline

[![CI](https://github.com/thanuz-26/fx-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/thanuz-26/fx-pipeline/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A containerized Python pipeline that downloads the daily ECB euro reference
rates from the Frankfurter API, checks them with eight data quality checks, and
loads them into PostgreSQL in a way that is safe to run again and again. Every
run and every check result is recorded in the database. The whole project runs
in Docker Compose and is tested automatically on every push.

## Business story

A risk team has exposures in many currencies and needs reliable, clean exchange
rates in one place to convert them to EUR. This pipeline gives them a single
PostgreSQL database with validated daily rates for USD, GBP, CHF, JPY and INR
against the euro. It also keeps the untouched API response for auditing, a log
of every run, and the result of every data quality check, so anyone can see
what was loaded, when, and how good the data was.