package com.antigravity.bountyhunter;

import android.app.Activity;
import android.content.Intent;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import androidx.activity.result.ActivityResult;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import java.util.ArrayList;
import java.util.Locale;

@CapacitorPlugin(
    name = "VoiceInput",
    permissions = {
        @Permission(
            alias = "audio",
            strings = { android.Manifest.permission.RECORD_AUDIO }
        )
    }
)
public class VoiceInputPlugin extends Plugin {

    @PluginMethod
    public void isAvailable(PluginCall call) {
        boolean available = SpeechRecognizer.isRecognitionAvailable(getContext());
        JSObject ret = new JSObject();
        ret.put("available", available);
        call.resolve(ret);
    }

    @PluginMethod
    public void promptSpeech(PluginCall call) {
        try {
            Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);

            String lang = call.getString("language", Locale.getDefault().toLanguageTag());
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, lang);
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, lang);
            intent.putExtra(RecognizerIntent.EXTRA_ONLY_RETURN_LANGUAGE_PREFERENCE, lang);

            String prompt = call.getString("prompt", "Di tu tarea o comando vocal...");
            intent.putExtra(RecognizerIntent.EXTRA_PROMPT, prompt);
            intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3);

            startActivityForResult(call, intent, "speechResult");
        } catch (Exception e) {
            call.reject("Error al iniciar reconocimiento vocal: " + e.getMessage());
        }
    }

    @ActivityCallback
    private void speechResult(PluginCall call, ActivityResult result) {
        if (call == null) {
            return;
        }

        JSObject ret = new JSObject();
        if (result.getResultCode() == Activity.RESULT_OK && result.getData() != null) {
            ArrayList<String> matches = result.getData().getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if (matches != null && !matches.isEmpty()) {
                ret.put("success", true);
                ret.put("text", matches.get(0));
                ret.put("matches", new com.getcapacitor.JSArray(matches));
                call.resolve(ret);
                return;
            }
        }

        ret.put("success", false);
        ret.put("text", "");
        call.resolve(ret);
    }
}
