from collections.abc import Sequence

import pandas as pd
from mlflow.metrics import MetricValue, make_metric
from mlflow.models import EvaluationMetric

from .base import (
    DEFAULT_JUDGE_INF_CONFIG,
    Aggregation,
    BaseLLMAsAJudgeMetric,
    aggregate_scores,
    extract_between_tags,
)
from ..bedrock import BedrockModel, extract_text_content_block


COMPLETENESS_PROMPT = """\
You are an expert medical professional tasked with evaluating the quality of a SOAP note based on a doctor-patient conversation transcript. Your specific focus is on assessing the "Completeness" of the SOAP note.
You will receive a complete transcript of a doctor-patient conversation and a corresponding SOAP note.
Your assessment will consist of a concise evaluation of the SOAP note and a score on a scale from 1 to 5 (higher is better).

<example>

<input>

<transcript>
Hello, I'm Doctor. Wilson. Welcome to our practice. Thank you for seeing me today. I see you're interested in discussing crow's feet treatment. Before we get into that, could you tell me about your medical history? I'm currently taking Ozempic for weight loss. I've lost about 20 pounds over the last six months. No other medical conditions. Are you experiencing any side effects from the Ozempic? Nope, it's been working well for me. Just the expected appetite suppression. Have you had any aesthetic treatments before? Yes, I had Botox about a year ago. The results were good, but I did get a mild headache afterwards. Thank you for sharing that. What specifically bothers you about your crow's feet? They're quite deep and they're affecting how my eye makeup looks. I feel like they're aging me. Would you be comfortable with me examining the area around your eyes? Yes, that's fine. I'm noting moderate crow's feet with dynamic movement and mild upper eyelid hooding. Your brow position is good. When you had Botox previously, do you recall how many units you received? I don't remember exactly. It was my first time trying it. And the headache you mentioned, how long did it last? Just a day or two. It wasn't severe. For your crow's feet, I would recommend twelve units of Botox on each side. Given your previous experience with headaches, we'll schedule your treatment when you have a light schedule the next day. How does that sound? That sounds reasonable. Would it affect my eye makeup application? You'll need to avoid eye makeup for twenty four hours after treatment. After that, you can resume your normal routine. Most patients find that their makeup applies more smoothly once the Botox takes effect. What about cost? The total cost would be $450 for both sides. We also offer a membership program that provides discounted rates for regular maintenance treatments. How often would I need to come back? Typically every three to four months for maintenance. Some patients find they can go longer between treatments once they've had several consistent sessions. And it's safe with Ozempic? Yes. There are no contraindications with Ozempic. However, if you experience any significant weight changes, it might affect how long your results last. Would you could I schedule the treatment? We could do it today if you'd like, or schedule for another time. Do you have any important events coming up? No major events planned. Would you like to proceed with treatment today? Yeah, think I would. Let me review the consent forms with you and then we can proceed with treatment.
</transcript>

<soap_note>
Subjective: Patient is concerned about deep crow's feet affecting appearance. Reports using Ozempic for weight loss and having had previous Botox treatment with a mild headache, but does not recall exact details.
Objective: Facial exam reveals moderate crow's feet with dynamic movement and normal brow position.
Assessment: Diagnosis: Age-related crow's feet.
Plan: Recommend 12 units of Botox per side with a post-treatment instruction to avoid eye makeup for 24 hours; treatment scheduled for today with follow-up maintenance every 3-4 months.
</soap_note>

</input>

<output>
<evaluation>
## Subjective
The note correctly mentions the patient's concern about deep crow's feet and the use of Ozempic, as well as a previous Botox treatment with a mild headache. However, it could have been improved by including specific details from the transcript such as the patient's weight loss of "about 20 pounds over the last six months" and more precise information on the headache duration ("a day or two").

## Objective
The objective section accurately identifies moderate crow's feet with dynamic movement and notes normal brow position. Yet, it misses the key detail regarding "mild upper eyelid hooding," which was noted during the examination. Including this finding would have provided a more complete clinical picture.

## Assessment
The assessment offers a clear diagnosis of age-related crow's feet.

## Plan
The treatment plan is clear, mentioning 12 units of Botox per side and advising on post-treatment care. It could be enhanced by including additional details such as the discussion about cost, the membership program, and the follow-up schedule, which are part of the transcript but absent in the note.

## Conclusion
Overall, while the SOAP note captures the core elements, it omits several key details, particularly in the subjective history and objective findings, that would have provided a fuller picture of the patient's condition and treatment considerations. This selective inclusion of information justifies a completeness score of **3 (Fair)**. Enhancing detail in each section would lead to a more comprehensive note.
</evaluation>
<score>3</score>

</output>

</example>

Definition of "Completeness":
Completeness measures the extent to which the SOAP note captures all the important medical information present in the original transcript. This includes key details about the patient's symptoms, medical history, examination findings, diagnosis, and treatment plan.
When evaluating Completeness, do not take into account any possible unmentioned details or interpretations (we have a separate metric for that). Focus solely on assessing whether the SOAP note captures all the important medical information present in the transcript.

5-point scoring rubric for Completeness:
1 - Completely Inadequate: The SOAP note misses most of the critical information from the transcript.
2 - Poor: The SOAP note omits several important details, only a partial reflection of the transcript is evident.
3 - Fair: The SOAP note captures most of the significant information, but a few key details or nuances are either missing or slightly inaccurate.
4 - Good: The SOAP note includes nearly all important information from the transcript, with only trivial omissions, but they do not affect the overall clinical understanding.
5 - Excellent: The SOAP note comprehensively captures all important information from the transcript without any significant omissions.

Instructions:
1. Carefully read the following transcript of a conversation between a doctor and a patient:

<transcript>
{transcript}
</transcript>

2. Now, review the SOAP note:

<soap_note>
{soap_note}
</soap_note>

3. Identify key information from the transcript that should be included in a complete SOAP note.
4. Assess how well the generated SOAP note captures this information.
5. Note any important information that was omitted.

Return the following information in your response:
    1. A concise evaluation of the SOAP note. Put it inside the <evaluation></evaluation> tags. In your evaluation, go over each section of the SOAP note first, writing down your notes or critique. In case of any mistakes in the SOAP note, you must explicitly specify what is wrong or how a particular section can be improved. After this, add a conclusion section, that summarizes your review.
    2. A single number representing your numerical score based on the rubric. Put it inside the <score></score> tags.
Do not add any other fields or lines to your response."""
SOURCE_GROUNDING_PROMPT = """\
You are an expert medical professional tasked with evaluating the quality of a SOAP note based on a doctor-patient conversation transcript. Your specific focus is on assessing the "Source Grounding" of the SOAP note.
You will receive a complete transcript of a doctor-patient conversation and a corresponding SOAP note.
Your assessment will consist of a concise evaluation of the SOAP note and a score on a scale from 1 to 5 (higher is better).

<example>

<input>

<transcript>
Hello, I'm Doctor. Wilson. Welcome to our practice. Thank you for seeing me today. I see you're interested in discussing crow's feet treatment. Before we get into that, could you tell me about your medical history? I'm currently taking Ozempic for weight loss. I've lost about 20 pounds over the last six months. No other medical conditions. Are you experiencing any side effects from the Ozempic? Nope, it's been working well for me. Just the expected appetite suppression. Have you had any aesthetic treatments before? Yes, I had Botox about a year ago. The results were good, but I did get a mild headache afterwards. Thank you for sharing that. What specifically bothers you about your crow's feet? They're quite deep and they're affecting how my eye makeup looks. I feel like they're aging me. Would you be comfortable with me examining the area around your eyes? Yes, that's fine. I'm noting moderate crow's feet with dynamic movement and mild upper eyelid hooding. Your brow position is good. When you had Botox previously, do you recall how many units you received? I don't remember exactly. It was my first time trying it. And the headache you mentioned, how long did it last? Just a day or two. It wasn't severe. For your crow's feet, I would recommend twelve units of Botox on each side. Given your previous experience with headaches, we'll schedule your treatment when you have a light schedule the next day. How does that sound? That sounds reasonable. Would it affect my eye makeup application? You'll need to avoid eye makeup for twenty four hours after treatment. After that, you can resume your normal routine. Most patients find that their makeup applies more smoothly once the Botox takes effect. What about cost? The total cost would be $450 for both sides. We also offer a membership program that provides discounted rates for regular maintenance treatments. How often would I need to come back? Typically every three to four months for maintenance. Some patients find they can go longer between treatments once they've had several consistent sessions. And it's safe with Ozempic? Yes. There are no contraindications with Ozempic. However, if you experience any significant weight changes, it might affect how long your results last. Would you could I schedule the treatment? We could do it today if you'd like, or schedule for another time. Do you have any important events coming up? No major events planned. Would you like to proceed with treatment today? Yeah, think I would. Let me review the consent forms with you and then we can proceed with treatment.
</transcript>

<soap_note>
Subjective: Patient expresses concerns about deep crow's feet negatively impacting her appearance and makeup application, and states that previous Botox resulted in a mild headache lasting a couple of days. She is currently taking Ozempic for weight loss without adverse effects.
Objective: Examination shows moderate, dynamic crow's feet with mild upper eyelid hooding. Additionally, slight periorbital dryness and subtle skin laxity are noted.
Assessment: The patient presents with cosmetic concerns primarily due to dynamic crow's feet. The minor findings of periorbital dryness and skin laxity were observed, suggesting early signs of skin aging.
Plan: Proceed with administering 12 units of Botox per side today. Advise the patient to avoid eye makeup for 24 hours post-procedure and schedule treatment on a lighter day. Plan for routine follow-up to evaluate treatment effectiveness.
</soap_note>

</input>

<output>
<evaluation>
## Subjective
The section accurately reflects the patient's concerns and medical history as mentioned in the transcript. No hallucinations are evident here.

## Objective
While the note correctly identifies moderate, dynamic crow's feet and mild upper eyelid hooding, it introduces "slight periorbital dryness" and "subtle skin laxity" which are not supported by the transcript.

## Assessment
The assessment appropriately addresses the cosmetic concern of crow's feet, but it extends the interpretation by linking dryness and laxity to early signs of aging—information that goes beyond what was provided.

## Plan
The treatment plan is mostly in line with the transcript. However, the mention of a "routine follow-up to evaluate treatment effectiveness" is an unwarranted addition not mentioned during the consultation.

## Conclusion
The SOAP note is mostly supported by the transcript, but the inclusion of several additional details and interpretations leads to a few instances of unsupported information. Therefore, it merits a score of **3 (Fair)**. Refining the note to strictly include only information directly mentioned in the transcript would improve its source grounding.
</evaluation>
<score>3</score>

</output>

</example>

Definition of "Source Grounding":
Source Grounding measures the extent to which the SOAP note includes only information that is directly supported by the transcript. A high Source Grounding score indicates that the SOAP note contains minimal or no hallucinations (completely made-up data) and avoids unwarranted interpretations that go beyond what the conversation provides.
When evaluating Source Grounding, do not take into account any possible omissions or understated details (we have a separate metric for that). Focus solely on assessing whether the SOAP note includes only information that is directly supported by the transcript.

5-point scoring rubric for Source Grounding:
1 - Completely Inadequate: The SOAP note is riddled with hallucinations or unsupported interpretations; most information is not found in the transcript.
2 - Poor: The SOAP note includes invented details or over-interpretations that aren’t supported by the transcript in many sections, reducing reliability.
3 - Fair: The SOAP note mostly aligns with the transcript, but there are a few minor instances of unsupported information or interpretations that slightly exceed the conversation's scope.
4 - Good: The SOAP note closely aligns with the transcript, with only one or two very minor discrepancies or slightly extended interpretations present, but they do not affect the overall clinical understanding.
5 - Excellent: The SOAP note is fully supported by the transcript, with no hallucinations or unwarranted interpretations.

Instructions:
1. Carefully read the following transcript of a conversation between a doctor and a patient:

<transcript>
{transcript}
</transcript>

2. Now, review the SOAP note:

<soap_note>
{soap_note}
</soap_note>

3. Identify any information in the SOAP note that is not directly supported by the transcript, including:
    a. Hallucinations (completely made-up data)
    b. Unwarranted interpretations that go beyond what the conversation provides
    c. Exaggerations or minimizations of symptoms or findings

Return the following information in your response:
    1. A concise evaluation of the SOAP note. Put it inside the <evaluation></evaluation> tags. In your evaluation, go over each section of the SOAP note first, writing down your notes or critique. In case of any mistakes in the SOAP note, you must explicitly specify what is wrong or how a particular section can be improved. After this, add a conclusion section, that summarizes your review.
    2. A single number representing your numerical score based on the rubric. Put it inside the <score></score> tags.
Do not add any other fields or lines to your response."""


class SOAPNoteMetric(BaseLLMAsAJudgeMetric):
    """Evaluation metric for assessing quality of generated SOAP notes using an LLM-as-a-Judge approach."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._assistant_response_prefill = "<evaluation>\n## Subjective"

    def make_mlflow_metric(
        self, judge_model: BedrockModel
    ) -> EvaluationMetric:
        """Creates an MLflow-compatible metric for SOAP note evaluation.

        Args:
            judge_model: An instance of `BedrockModel` to calculate the metric.

        Returns:
            An `EvaluationMetric` instance compatible with MLflow.
        """
        def eval_fn(
            predictions: pd.Series, transcript: pd.Series
        ) -> MetricValue:
            scores = []
            evals = []
            for pred, tr in zip(predictions, transcript):
                messages = [self.prompt.format(transcript=tr, soap_note=pred)]
                if not judge_model.is_reasoner:
                    messages.append(self._assistant_response_prefill)
                if judge_model.inf_config is None:
                    response = judge_model(
                        messages, inferenceConfig=DEFAULT_JUDGE_INF_CONFIG
                    )
                else:
                    response = judge_model(messages)
                message = extract_text_content_block(response)["text"]
                if not judge_model.is_reasoner:
                    message = self._assistant_response_prefill + message
                scores.append(int(extract_between_tags("score", message)[0]))
                evals.append(extract_between_tags("evaluation", message)[0])
            return MetricValue(
                scores, evals, aggregate_scores(scores, self.aggregations)
            )
        return make_metric(
            eval_fn=eval_fn,
            greater_is_better=self.greater_is_better,
            name=self.name,
        )


def completeness(
    aggregations: Sequence[Aggregation] | None = None
) -> SOAPNoteMetric:
    """Returns a `SOAPNoteMetric` instance for evaluating completeness of SOAP notes.

    Args:
        aggregations: Optional list of aggregations to apply.

    Returns:
        A configured `SOAPNoteMetric` instance.
    """
    return SOAPNoteMetric("completeness", COMPLETENESS_PROMPT, aggregations)


def source_grounding(
    aggregations: Sequence[Aggregation] | None = None
) -> SOAPNoteMetric:
    """Returns a `SOAPNoteMetric` instance for evaluating source grounding of SOAP notes.

    Args:
        aggregations: Optional list of aggregations to apply.

    Returns:
        A configured `SOAPNoteMetric` instance.
    """
    return SOAPNoteMetric(
        "source_grounding", SOURCE_GROUNDING_PROMPT, aggregations
    )