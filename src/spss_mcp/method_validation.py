from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class MethodParams(BaseModel):
    model_config = {"extra": "forbid"}


class CaseSelectionParams(MethodParams):
    filter_variable: Optional[str] = None
    select_if: Optional[str] = None

    @model_validator(mode="after")
    def validate_selection(self) -> "CaseSelectionParams":
        if self.filter_variable and self.select_if:
            raise ValueError("filter_variable and select_if cannot both be provided")
        if not self.filter_variable and not self.select_if:
            raise ValueError("At least one case selection option must be provided")
        return self


class LogisticRegressionParams(MethodParams):
    dependent: str
    predictors: list[str] = Field(min_length=1)
    method: Literal["ENTER", "FSTEP", "BSTEP"] = "ENTER"
    categorical: Optional[list[str]] = None
    contrast: Optional[str] = None
    save_predicted: bool = False
    print_options: Optional[list[str]] = None


class OrdinalRegressionParams(MethodParams):
    dependent: str
    predictors: list[str] = Field(min_length=1)
    link: Literal["LOGIT", "PROBIT", "CLOGLOG", "NLOGLOG", "CAUCHIT"] = "LOGIT"
    categorical: Optional[list[str]] = None
    save_predicted: bool = False
    test_parallel: bool = True


class GenlinParams(MethodParams):
    dependent: str
    predictors: list[str] = Field(min_length=1)
    distribution: Literal[
        "NORMAL", "BINOMIAL", "POISSON", "GAMMA", "IGAUSS", "NEGBIN", "MULTINOMIAL"
    ] = "NORMAL"
    link: Optional[str] = None
    scale: Optional[str] = None
    categorical: Optional[list[str]] = None
    save_predicted: bool = False


class MixedParams(MethodParams):
    dependent: str
    fixed_effects: list[str] = Field(min_length=1)
    random_effects: Optional[list[str]] = None
    subject: Optional[str] = None
    repeated: Optional[str] = None
    repeated_type: Optional[str] = None
    method: Literal["REML", "ML"] = "REML"
    covtype_random: Optional[str] = None

    @model_validator(mode="after")
    def validate_dependencies(self) -> "MixedParams":
        if self.random_effects and not self.subject:
            raise ValueError("subject is required when random_effects are provided")
        if self.repeated and not self.subject:
            raise ValueError("subject is required when repeated is provided")
        return self


class GenlinMixedParams(MethodParams):
    dependent: str
    fixed_effects: list[str] = Field(min_length=1)
    random_effects: Optional[list[str]] = None
    subject: Optional[str] = None
    distribution: Literal["NORMAL", "BINOMIAL", "POISSON", "GAMMA", "NEGBIN"] = "NORMAL"
    link: Optional[str] = None

    @model_validator(mode="after")
    def validate_subject(self) -> "GenlinMixedParams":
        if self.random_effects and not self.subject:
            raise ValueError("subject is required when random_effects are provided")
        return self


class CoxRegressionParams(MethodParams):
    time_variable: str
    status_variable: str
    status_event_value: int | str
    predictors: list[str] = Field(min_length=1)
    method: Literal["ENTER", "FSTEP", "BSTEP"] = "ENTER"
    categorical: Optional[list[str]] = None
    strata: Optional[list[str]] = None
    save_survival: bool = False


class KaplanMeierParams(MethodParams):
    time_variable: str
    status_variable: str
    status_event_value: int | str
    strata: Optional[str] = None
    compare_method: Literal["LOGRANK", "BRESLOW", "TARONE"] = "LOGRANK"
    percentiles: Optional[list[int]] = None


class DiscriminantParams(MethodParams):
    groups: str
    group_values: Optional[list[int]] = None
    predictors: list[str] = Field(min_length=1)
    method: Literal["DIRECT", "WILKS", "MAHAL"] = "DIRECT"
    priors: Literal["EQUAL", "SIZE"] = "EQUAL"
    save_scores: bool = False
    save_class: bool = False


class HierarchicalClusterParams(MethodParams):
    variables: list[str] = Field(min_length=1)
    method: Literal[
        "BAVERAGE", "WAVERAGE", "SINGLE", "COMPLETE", "CENTROID", "MEDIAN", "WARD"
    ] = "WARD"
    measure: Literal[
        "SEUCLID",
        "EUCLID",
        "COSINE",
        "PEARSON",
        "CHEBYCHEV",
        "BLOCK",
        "MINKOWSKI",
        "CUSTOMIZED",
    ] = "SEUCLID"
    id_variable: Optional[str] = None
    dendrogram: bool = True


class TwoStepClusterParams(MethodParams):
    continuous: Optional[list[str]] = None
    categorical: Optional[list[str]] = None
    distance: Literal["LIKELIHOOD", "EUCLIDEAN"] = "LIKELIHOOD"
    num_clusters: Optional[int] = None
    max_clusters: int = 15
    outlier_handling: bool = True

    @model_validator(mode="after")
    def validate_inputs(self) -> "TwoStepClusterParams":
        if not self.continuous and not self.categorical:
            raise ValueError(
                "Must specify at least one continuous or categorical variable"
            )
        if self.num_clusters is not None and self.num_clusters < 1:
            raise ValueError("num_clusters must be at least 1")
        if self.max_clusters < 2:
            raise ValueError("max_clusters must be at least 2")
        return self


class ManovaParams(MethodParams):
    dependents: list[str] = Field(min_length=2)
    factors: list[str] = Field(min_length=1)
    factor_ranges: Optional[dict[str, list[int]]] = None
    covariates: Optional[list[str]] = None
    method: Literal["SSTYPE1", "SSTYPE2", "SSTYPE3", "SSTYPE4"] = "SSTYPE3"
    print_multivariate: bool = True
    print_univariate: bool = True


class GlmUnivariateParams(MethodParams):
    dependent: str
    factors: list[str] = Field(min_length=1)
    covariates: Optional[list[str]] = None
    emmeans: Optional[list[str]] = None
    posthoc: Optional[list[str]] = None
    posthoc_method: Optional[str] = None
    save_predicted: bool = False

    @model_validator(mode="after")
    def validate_posthoc(self) -> "GlmUnivariateParams":
        if self.posthoc and not self.posthoc_method:
            raise ValueError(
                "posthoc_method is required when posthoc variables are provided"
            )
        return self


class ProcessParams(MethodParams):
    """Validated parameters for Hayes PROCESS model 4.

    Model 4 supports one mediator or multiple parallel mediators.  Keeping the
    first release to one well-defined model prevents silently generating a
    different causal graph than the caller intended.
    """

    x: str
    y: str
    mediators: list[str] = Field(min_length=1, max_length=10)
    model: Literal[4] = 4
    covariates: Optional[list[str]] = None
    confidence: float = Field(default=95.0, gt=50.0, lt=100.0)
    bootstrap_samples: int = Field(default=5000, ge=1000, le=100000)
    total_effect: bool = True
    pairwise_contrasts: bool = True
    effect_size: bool = True
    standardized_coefficients: bool = False
    normal_theory_test: bool = False
    seed: Optional[int] = Field(default=None, ge=1, le=2147483646)

    @field_validator("x", "y")
    @classmethod
    def validate_scalar_variable(cls, value: str) -> str:
        return cls._validate_variable(value)

    @field_validator("mediators", "covariates")
    @classmethod
    def validate_variable_list(cls, values: Optional[list[str]]) -> Optional[list[str]]:
        if values is None:
            return None
        return [cls._validate_variable(value) for value in values]

    @staticmethod
    def _validate_variable(value: str) -> str:
        value = value.strip()
        if not value or len(value) > 64:
            raise ValueError("SPSS variable names must contain 1-64 characters")
        first = value[0]
        if not (first.isalpha() or first in "@#$"):
            raise ValueError(f"Invalid SPSS variable name: {value!r}")
        if not all(char.isalnum() or char in "_@#$" for char in value[1:]):
            raise ValueError(f"Invalid SPSS variable name: {value!r}")
        return value

    @model_validator(mode="after")
    def validate_roles(self) -> "ProcessParams":
        mediators = list(self.mediators)
        covariates = list(self.covariates or [])
        all_variables = [self.x, self.y, *mediators, *covariates]
        folded = [value.casefold() for value in all_variables]
        if len(folded) != len(set(folded)):
            raise ValueError("X, Y, mediators, and covariates must be distinct")
        return self
